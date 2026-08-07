"""운영 DB 읽기/쓰기 (집계·메타·타겟 포착/점검 우선순위 조회용)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.ops_db.db import connect, init_db
from src.scoring.ops_capture import CASE_PRIMARY_AUX, OpsPairSpec, OPS_PAIR_SPECS
from src.scoring.ops_queue import (
    ACTUAL_COL,
    AUX_LABELS,
    CB_GRADE_COL,
    CB_SCORE_COL,
    CELL_COL,
    GRADE_COL,
    PRED_COL,
    PRIMARY_LABELS,
    PRIORITY_COL,
    RF_SCORE_COL,
    empty_band_matrix,
)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class OpsRepository:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        init_db(cfg)

    def create_run(
        self,
        run_id: str,
        *,
        operator: str = "",
        work_content: str = "",
        note: str = "",
        config: dict | None = None,
    ) -> None:
        """새 Run 발급 (작업자·작업내용·비고 포함)."""
        with connect(self.cfg) as conn:
            conn.execute(
                """
                INSERT INTO runs(
                    run_id, created_at, operator, work_content, note, status, config_json
                )
                VALUES (?, ?, ?, ?, ?, 'active', ?)
                """,
                (
                    run_id,
                    _now(),
                    operator.strip(),
                    work_content.strip(),
                    note.strip(),
                    json.dumps(config or {}, ensure_ascii=False),
                ),
            )
            conn.commit()

    def ensure_run(self, run_id: str, note: str = "", config: dict | None = None) -> None:
        """Run 행이 없으면 생성. 이미 있으면 메타(작업자 등)를 덮어쓰지 않음."""
        with connect(self.cfg) as conn:
            exists = conn.execute(
                "SELECT 1 FROM runs WHERE run_id=?", (run_id,)
            ).fetchone()
            if exists:
                if config is not None:
                    conn.execute(
                        "UPDATE runs SET config_json=? WHERE run_id=?",
                        (json.dumps(config, ensure_ascii=False), run_id),
                    )
            else:
                conn.execute(
                    """
                    INSERT INTO runs(
                        run_id, created_at, operator, work_content, note, status, config_json
                    )
                    VALUES (?, ?, '', '', ?, 'active', ?)
                    """,
                    (
                        run_id,
                        _now(),
                        note,
                        json.dumps(config or {}, ensure_ascii=False),
                    ),
                )
            conn.commit()

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with connect(self.cfg) as conn:
            rows = conn.execute(
                "SELECT * FROM runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_latest_run_id(self) -> str | None:
        runs = self.list_runs(1)
        return runs[0]["run_id"] if runs else None

    def upsert_step(
        self,
        run_id: str,
        step_id: str,
        status: str,
        message: str = "",
        log_path: str = "",
        *,
        started: bool = False,
        ended: bool = False,
    ) -> None:
        self.ensure_run(run_id)
        with connect(self.cfg) as conn:
            existing = conn.execute(
                "SELECT started_at FROM run_steps WHERE run_id=? AND step_id=?",
                (run_id, step_id),
            ).fetchone()
            started_at = existing["started_at"] if existing else None
            if started or not started_at:
                started_at = _now()
            ended_at = _now() if ended else None
            conn.execute(
                """
                INSERT INTO run_steps(run_id, step_id, status, started_at, ended_at, message, log_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, step_id) DO UPDATE SET
                    status=excluded.status,
                    started_at=COALESCE(run_steps.started_at, excluded.started_at),
                    ended_at=excluded.ended_at,
                    message=excluded.message,
                    log_path=excluded.log_path
                """,
                (run_id, step_id, status, started_at, ended_at, message, log_path),
            )
            conn.commit()

    def list_steps(self, run_id: str) -> list[dict[str, Any]]:
        with connect(self.cfg) as conn:
            rows = conn.execute(
                "SELECT * FROM run_steps WHERE run_id=? ORDER BY started_at",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_step(self, run_id: str, step_id: str) -> dict[str, Any] | None:
        with connect(self.cfg) as conn:
            row = conn.execute(
                "SELECT * FROM run_steps WHERE run_id=? AND step_id=?",
                (run_id, step_id),
            ).fetchone()
        return dict(row) if row else None

    def step_succeeded(self, run_id: str, step_id: str) -> bool:
        row = self.get_step(run_id, step_id)
        return bool(row and row.get("status") == "succeeded")

    def delete_steps(self, run_id: str, step_ids: list[str]) -> int:
        """단계 이력 행 삭제 (미실행으로 되돌림)."""
        if not step_ids:
            return 0
        with connect(self.cfg) as conn:
            placeholders = ",".join("?" * len(step_ids))
            cur = conn.execute(
                f"DELETE FROM run_steps WHERE run_id=? AND step_id IN ({placeholders})",
                (run_id, *step_ids),
            )
            conn.commit()
            return int(cur.rowcount or 0)

    def clear_ranking(self, run_id: str) -> None:
        with connect(self.cfg) as conn:
            conn.execute("DELETE FROM model_ranking WHERE run_id=?", (run_id,))
            conn.commit()

    def clear_ops_queue(self, run_id: str) -> None:
        with connect(self.cfg) as conn:
            conn.execute("DELETE FROM ops_queue_rows WHERE run_id=?", (run_id,))
            conn.execute(
                "DELETE FROM ops_queue_entity_rows WHERE run_id=?", (run_id,)
            )
            conn.commit()

    def save_ranking(self, run_id: str, ranking: list[dict[str, Any]]) -> None:
        self.ensure_run(run_id)
        with connect(self.cfg) as conn:
            conn.execute("DELETE FROM model_ranking WHERE run_id=?", (run_id,))
            for row in ranking:
                conn.execute(
                    """
                    INSERT INTO model_ranking(
                        run_id, rank, algo, role, pr_auc, roc_auc, top1_lift, f1,
                        top1_precision, top1_recall, top5_lift, top5_precision, top5_recall
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        int(row["rank"]),
                        row["algo"],
                        row["role"],
                        row.get("pr_auc"),
                        row.get("roc_auc"),
                        row.get("top1_lift"),
                        row.get("f1"),
                        row.get("top1_precision"),
                        row.get("top1_recall"),
                        row.get("top5_lift"),
                        row.get("top5_precision"),
                        row.get("top5_recall"),
                    ),
                )
            conn.commit()

    def get_ranking(self, run_id: str) -> list[dict[str, Any]]:
        with connect(self.cfg) as conn:
            rows = conn.execute(
                "SELECT * FROM model_ranking WHERE run_id=? ORDER BY rank, algo",
                (run_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_primary_aux(self, run_id: str | None = None) -> tuple[str, str]:
        rid = run_id or self.get_latest_run_id()
        if not rid:
            ops = self.cfg.get("ops_queue", {})
            return (
                ops.get("primary_algo", "random_forest_v1"),
                ops.get("aux_algo", "catboost_v1"),
            )
        ranking = self.get_ranking(rid)
        primary = next((r["algo"] for r in ranking if r["role"] == "primary"), None)
        aux = next((r["algo"] for r in ranking if r["role"] == "aux"), None)
        ops = self.cfg.get("ops_queue", {})
        return (
            primary or ops.get("primary_algo", "random_forest_v1"),
            aux or ops.get("aux_algo", "catboost_v1"),
        )

    def filename_exists(self, filename: str, *, dataset_kind: str = "train") -> bool:
        kind = "inference" if dataset_kind == "inference" else "train"
        with connect(self.cfg) as conn:
            if kind == "inference":
                row = conn.execute(
                    "SELECT 1 FROM raw_inference_registry WHERE filename=? LIMIT 1",
                    (filename,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT 1 FROM raw_registry
                    WHERE filename=? AND COALESCE(dataset_kind,'train')='train'
                    LIMIT 1
                    """,
                    (filename,),
                ).fetchone()
        return row is not None

    def register_raw_file(
        self,
        filename: str,
        rel_path: str,
        row_count: int | None = None,
        file_sha256: str | None = None,
        note: str = "",
        *,
        dataset_kind: str = "train",
        selected: bool = True,
    ) -> None:
        """dataset_kind: train | inference. 신규 업로드는 기본 선택(selected=1)."""
        kind = "inference" if dataset_kind == "inference" else "train"
        table = "raw_inference_registry" if kind == "inference" else "raw_registry"
        sel = 1 if selected else 0
        with connect(self.cfg) as conn:
            if table == "raw_registry":
                conn.execute(
                    """
                    INSERT INTO raw_registry(
                        registered_at, filename, rel_path, row_count,
                        file_sha256, note, dataset_kind, selected
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_now(), filename, rel_path, row_count, file_sha256, note, kind, sel),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO raw_inference_registry(
                        registered_at, filename, rel_path, row_count,
                        file_sha256, note, selected
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_now(), filename, rel_path, row_count, file_sha256, note, sel),
                )
            conn.commit()

    def set_raw_selection(self, ids: list[int], *, dataset_kind: str = "train") -> int:
        """해당 kind의 selected를 주어진 id만 1, 나머지 0으로 설정. 선택된 개수 반환."""
        kind = "inference" if dataset_kind == "inference" else "train"
        table = "raw_inference_registry" if kind == "inference" else "raw_registry"
        id_set = {int(i) for i in ids}
        with connect(self.cfg) as conn:
            if kind == "train":
                conn.execute(
                    "UPDATE raw_registry SET selected=0 WHERE COALESCE(dataset_kind,'train')='train'"
                )
                rows = conn.execute(
                    """
                    SELECT id FROM raw_registry
                    WHERE COALESCE(dataset_kind,'train')='train'
                    """
                ).fetchall()
            else:
                conn.execute(f"UPDATE {table} SET selected=0")
                rows = conn.execute(f"SELECT id FROM {table}").fetchall()
            n = 0
            for r in rows:
                rid = int(r["id"])
                if rid in id_set:
                    conn.execute(
                        f"UPDATE {table} SET selected=1 WHERE id=?",
                        (rid,),
                    )
                    n += 1
            conn.commit()
        return n

    def list_selected_rel_paths(self, *, dataset_kind: str = "train") -> list[str]:
        kind = "inference" if dataset_kind == "inference" else "train"
        with connect(self.cfg) as conn:
            if kind == "inference":
                rows = conn.execute(
                    """
                    SELECT rel_path FROM raw_inference_registry
                    WHERE COALESCE(selected, 0)=1
                    ORDER BY id ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT rel_path FROM raw_registry
                    WHERE COALESCE(dataset_kind,'train')='train'
                      AND COALESCE(selected, 0)=1
                    ORDER BY id ASC
                    """
                ).fetchall()
        return [str(r["rel_path"]).replace("\\", "/") for r in rows if r["rel_path"]]

    def list_raw_registry(
        self, limit: int = 200, *, dataset_kind: str = "train"
    ) -> list[dict[str, Any]]:
        kind = "inference" if dataset_kind == "inference" else "train"
        with connect(self.cfg) as conn:
            if kind == "inference":
                rows = conn.execute(
                    "SELECT * FROM raw_inference_registry ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT * FROM raw_registry
                    WHERE COALESCE(dataset_kind,'train')='train'
                    ORDER BY id DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def count_raw_registry(self, *, dataset_kind: str = "train") -> int:
        kind = "inference" if dataset_kind == "inference" else "train"
        with connect(self.cfg) as conn:
            if kind == "inference":
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM raw_inference_registry"
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT COUNT(*) AS n FROM raw_registry
                    WHERE COALESCE(dataset_kind,'train')='train'
                    """
                ).fetchone()
        return int(row["n"] if row else 0)

    def delete_raw_registry_ids(
        self, ids: list[int], *, dataset_kind: str = "train"
    ) -> list[dict[str, Any]]:
        """메타 삭제 후 삭제된 행(파일 경로용)을 반환. 남은 행 id는 1..N으로 재부여."""
        if not ids:
            return []
        kind = "inference" if dataset_kind == "inference" else "train"
        table = "raw_inference_registry" if kind == "inference" else "raw_registry"
        placeholders = ",".join("?" for _ in ids)
        with connect(self.cfg) as conn:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE id IN ({placeholders})",
                ids,
            ).fetchall()
            deleted = [dict(r) for r in rows]
            conn.execute(
                f"DELETE FROM {table} WHERE id IN ({placeholders})",
                ids,
            )
            self._reindex_registry_table(conn, table, dataset_kind=kind)
            conn.commit()
        return deleted

    def clear_raw_registry(self, *, dataset_kind: str = "train") -> list[dict[str, Any]]:
        """전체 메타 삭제. 삭제 전 행 목록 반환."""
        kind = "inference" if dataset_kind == "inference" else "train"
        table = "raw_inference_registry" if kind == "inference" else "raw_registry"
        with connect(self.cfg) as conn:
            if kind == "train":
                rows = conn.execute(
                    "SELECT * FROM raw_registry WHERE COALESCE(dataset_kind,'train')='train'"
                ).fetchall()
                conn.execute(
                    "DELETE FROM raw_registry WHERE COALESCE(dataset_kind,'train')='train'"
                )
            else:
                rows = conn.execute(f"SELECT * FROM {table}").fetchall()
                conn.execute(f"DELETE FROM {table}")
            self._reindex_registry_table(conn, table, dataset_kind=kind)
            conn.commit()
        return [dict(r) for r in rows]

    def _reindex_registry_table(
        self, conn: Any, table: str, *, dataset_kind: str
    ) -> None:
        """남은 행의 id를 등록 시각·기존 id 순으로 1..N 재부여하고 AUTOINCREMENT 동기화."""
        if table == "raw_registry" and dataset_kind == "train":
            where = "WHERE COALESCE(dataset_kind,'train')='train'"
        else:
            where = ""
        rows = conn.execute(
            f"SELECT * FROM {table} {where} ORDER BY id ASC"
        ).fetchall()
        rows = [dict(r) for r in rows]
        if table == "raw_registry" and dataset_kind == "train":
            conn.execute(
                "DELETE FROM raw_registry WHERE COALESCE(dataset_kind,'train')='train'"
            )
        else:
            conn.execute(f"DELETE FROM {table}")

        if table == "raw_registry":
            cols = (
                "id, registered_at, filename, rel_path, row_count, "
                "file_sha256, note, dataset_kind, selected"
            )
            for new_id, r in enumerate(rows, start=1):
                conn.execute(
                    f"""
                    INSERT INTO raw_registry({cols})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id,
                        r.get("registered_at"),
                        r.get("filename"),
                        r.get("rel_path"),
                        r.get("row_count"),
                        r.get("file_sha256"),
                        r.get("note"),
                        r.get("dataset_kind") or "train",
                        int(r.get("selected") if r.get("selected") is not None else 1),
                    ),
                )
        else:
            cols = (
                "id, registered_at, filename, rel_path, row_count, "
                "file_sha256, note, selected"
            )
            for new_id, r in enumerate(rows, start=1):
                conn.execute(
                    f"""
                    INSERT INTO raw_inference_registry({cols})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        new_id,
                        r.get("registered_at"),
                        r.get("filename"),
                        r.get("rel_path"),
                        r.get("row_count"),
                        r.get("file_sha256"),
                        r.get("note"),
                        int(r.get("selected") if r.get("selected") is not None else 1),
                    ),
                )

        # sqlite_sequence 동기화 (다음 AUTOINCREMENT가 N+1부터)
        max_id = len(rows)
        seq = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone()
        if seq:
            conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (table,))
            if max_id > 0:
                conn.execute(
                    "INSERT INTO sqlite_sequence(name, seq) VALUES (?, ?)",
                    (table, max_id),
                )

    def get_roles(self, run_id: str | None = None) -> dict[str, str | None]:
        rid = run_id or self.get_latest_run_id()
        primary, aux = self.get_primary_aux(rid)
        reference = None
        if rid:
            ranking = self.get_ranking(rid)
            reference = next(
                (r["algo"] for r in ranking if r.get("role") == "reference"), None
            )
        return {"primary": primary, "aux": aux, "reference": reference}

    def replace_ops_queue(self, run_id: str, queue_df: pd.DataFrame) -> int:
        """하위 호환: primary_aux PK queue만 적재."""
        return self.replace_ops_capture_pk(run_id, CASE_PRIMARY_AUX, queue_df)

    def replace_ops_capture(
        self,
        run_id: str,
        pk_queues: list[pd.DataFrame],
        entity_queues: list[pd.DataFrame],
    ) -> tuple[int, int]:
        self.ensure_run(run_id)
        init_db(self.cfg)
        pk_n = 0
        ent_n = 0
        with connect(self.cfg) as conn:
            conn.execute("DELETE FROM ops_queue_rows WHERE run_id=?", (run_id,))
            conn.execute(
                "DELETE FROM ops_queue_entity_rows WHERE run_id=?", (run_id,)
            )
            for q in pk_queues:
                if q is None or q.empty:
                    continue
                pk_n += self._insert_pk_queue(conn, run_id, q)
            for q in entity_queues:
                if q is None or q.empty:
                    continue
                ent_n += self._insert_entity_queue(conn, run_id, q)
            conn.commit()
        return pk_n, ent_n

    def replace_ops_capture_pk(
        self, run_id: str, case_id: str, queue_df: pd.DataFrame
    ) -> int:
        self.ensure_run(run_id)
        init_db(self.cfg)
        with connect(self.cfg) as conn:
            conn.execute(
                "DELETE FROM ops_queue_rows WHERE run_id=? AND case_id=?",
                (run_id, case_id),
            )
            n = self._insert_pk_queue(conn, run_id, queue_df)
            conn.commit()
        return n

    def _insert_pk_queue(
        self, conn: Any, run_id: str, queue_df: pd.DataFrame
    ) -> int:
        from src.scoring.ops_capture import CASE_ID_COL

        keys = self.cfg.get("key_columns", ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"])
        spec = _spec_for_queue(queue_df)
        case_id = (
            str(queue_df[CASE_ID_COL].iloc[0])
            if CASE_ID_COL in queue_df.columns
            else CASE_PRIMARY_AUX
        )
        rows = [
            self._queue_row_tuple(run_id, case_id, row, spec, keys)
            for _, row in queue_df.iterrows()
        ]
        conn.executemany(
            """
            INSERT INTO ops_queue_rows(
                run_id, case_id, crtr_ym, pfm_biz_id, inst_id, biz_nm, inst_nm,
                sbat_amt, pyhwy_amt, score_primary, score_aux,
                ops_grade, cross_check, grade_aux, priority,
                pred_label, actual_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def _insert_entity_queue(
        self, conn: Any, run_id: str, queue_df: pd.DataFrame
    ) -> int:
        from src.scoring.ops_capture import CASE_ID_COL

        spec = _spec_for_queue(queue_df)
        case_id = (
            str(queue_df[CASE_ID_COL].iloc[0])
            if CASE_ID_COL in queue_df.columns
            else CASE_PRIMARY_AUX
        )
        rows = []
        for _, row in queue_df.iterrows():
            pri = _row_get(row, PRIORITY_COL)
            try:
                pri_i = int(pri) if pri is not None and str(pri) != "" else None
            except (TypeError, ValueError):
                pri_i = None
            rows.append(
                (
                    run_id,
                    case_id,
                    str(_row_get(row, "PFM_BIZ_ID") or ""),
                    str(_row_get(row, "INST_ID") or ""),
                    str(_row_get(row, "수행사업명칭(PFM_BIZ_NM)") or ""),
                    str(_row_get(row, "기관명(INST_NM)") or ""),
                    str(_row_get(row, "사업비보조금금액(BIZCT_SBAT_AMT)") or ""),
                    str(_row_get(row, "사업비자부담금액(BIZCT_PYHWY_AMT)") or ""),
                    _to_float(_row_get(row, spec.row_score_col)),
                    _to_float(_row_get(row, spec.col_score_col)),
                    str(_row_get(row, spec.row_grade_col) or ""),
                    str(_row_get(row, spec.col_grade_col) or ""),
                    str(_row_get(row, CELL_COL) or ""),
                    pri_i,
                    str(_row_get(row, PRED_COL) if PRED_COL in row.index else ""),
                    str(_row_get(row, ACTUAL_COL) if ACTUAL_COL in row.index else ""),
                )
            )
        conn.executemany(
            """
            INSERT INTO ops_queue_entity_rows(
                run_id, case_id, pfm_biz_id, inst_id, biz_nm, inst_nm,
                sbat_amt, pyhwy_amt, score_row, score_col,
                ops_grade, grade_col, cross_check, priority,
                pred_label, actual_label
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        return len(rows)

    def _queue_row_tuple(
        self,
        run_id: str,
        case_id: str,
        row: pd.Series,
        spec: OpsPairSpec,
        keys: list[str],
    ) -> tuple:
        col_ym, col_biz, col_inst = keys[0], keys[1], keys[2]
        pri = _row_get(row, PRIORITY_COL)
        try:
            pri_i = int(pri) if pri is not None and str(pri) != "" else None
        except (TypeError, ValueError):
            pri_i = None
        return (
            run_id,
            case_id,
            str(_row_get(row, col_ym) or ""),
            str(_row_get(row, col_biz) or ""),
            str(_row_get(row, col_inst) or ""),
            str(_row_get(row, "수행사업명칭(PFM_BIZ_NM)") or ""),
            str(_row_get(row, "기관명(INST_NM)") or ""),
            str(_row_get(row, "사업비보조금금액(BIZCT_SBAT_AMT)") or ""),
            str(_row_get(row, "사업비자부담금액(BIZCT_PYHWY_AMT)") or ""),
            _to_float(_row_get(row, spec.row_score_col)),
            _to_float(_row_get(row, spec.col_score_col)),
            str(_row_get(row, spec.row_grade_col) or ""),
            str(_row_get(row, CELL_COL) or ""),
            str(_row_get(row, spec.col_grade_col) or ""),
            pri_i,
            str(_row_get(row, PRED_COL) if PRED_COL in row.index else ""),
            str(_row_get(row, ACTUAL_COL) if ACTUAL_COL in row.index else ""),
        )

    def ops_queue_summary(self, run_id: str) -> pd.DataFrame:
        df = self.ops_capture_summary(run_id, CASE_PRIMARY_AUX)
        if df.empty:
            return df
        out = df.copy()
        if "count_pk" in out.columns:
            out = out.rename(columns={"count_pk": "cnt"})
        return out

    def ops_capture_summary(self, run_id: str, case_id: str) -> pd.DataFrame:
        spec = _spec_by_id(case_id)
        with connect(self.cfg) as conn:
            pk_rows = conn.execute(
                """
                SELECT ops_grade AS row_band, grade_aux AS col_band,
                       cross_check AS cell, MIN(priority) AS priority,
                       COUNT(*) AS count_pk
                FROM ops_queue_rows
                WHERE run_id=? AND case_id=?
                GROUP BY ops_grade, grade_aux, cross_check
                ORDER BY COALESCE(MIN(priority), 99), ops_grade, grade_aux
                """,
                (run_id, case_id),
            ).fetchall()
            ent_rows = conn.execute(
                """
                SELECT ops_grade AS row_band, grade_col AS col_band,
                       cross_check AS cell, MIN(priority) AS priority,
                       COUNT(*) AS count_entity
                FROM ops_queue_entity_rows
                WHERE run_id=? AND case_id=?
                GROUP BY ops_grade, grade_col, cross_check
                ORDER BY COALESCE(MIN(priority), 99), ops_grade, grade_col
                """,
                (run_id, case_id),
            ).fetchall()

        pk_df = pd.DataFrame([dict(r) for r in pk_rows])
        ent_df = pd.DataFrame([dict(r) for r in ent_rows])
        if pk_df.empty and ent_df.empty:
            return pd.DataFrame()
        if pk_df.empty:
            out = ent_df.copy()
            out["count_pk"] = 0
        elif ent_df.empty:
            out = pk_df.copy()
            out["count_entity"] = 0
        else:
            out = pk_df.merge(
                ent_df[["cell", "priority", "count_entity"]],
                on=["cell", "priority"],
                how="outer",
            )
            out["count_pk"] = out["count_pk"].fillna(0).astype(int)
            out["count_entity"] = out["count_entity"].fillna(0).astype(int)
        if spec:
            out["row_axis"] = spec.row_prefix
            out["col_axis"] = spec.col_prefix
        return out

    def ops_queue_matrices(
        self, run_id: str
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
        return self.ops_capture_matrices(run_id, CASE_PRIMARY_AUX, unit="pk")

    def ops_capture_matrices(
        self,
        run_id: str,
        case_id: str,
        *,
        unit: str = "pk",
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
        spec = _spec_by_id(case_id)
        if spec is None:
            return empty_band_matrix(), empty_band_matrix(), {"total": 0, "positive": 0}

        table = "ops_queue_rows" if unit == "pk" else "ops_queue_entity_rows"
        col_field = "grade_aux" if unit == "pk" else "grade_col"

        with connect(self.cfg) as conn:
            all_rows = conn.execute(
                f"""
                SELECT ops_grade, {col_field} AS grade_col, COUNT(*) AS cnt
                FROM {table}
                WHERE run_id=? AND case_id=?
                GROUP BY ops_grade, {col_field}
                """,
                (run_id, case_id),
            ).fetchall()
            pos_rows = conn.execute(
                f"""
                SELECT ops_grade, {col_field} AS grade_col, COUNT(*) AS cnt
                FROM {table}
                WHERE run_id=? AND case_id=?
                  AND LOWER(TRIM(COALESCE(actual_label, '')))
                      IN ('1', '1.0', 'y', 'yes', 'true', 't')
                GROUP BY ops_grade, {col_field}
                """,
                (run_id, case_id),
            ).fetchall()

        matrix_all = _band_counts_to_matrix(all_rows, spec)
        matrix_pos = _band_counts_to_matrix(pos_rows, spec)
        total = int(matrix_all.to_numpy().sum())
        pos_total = int(matrix_pos.to_numpy().sum())
        return matrix_all, matrix_pos, {"total": total, "positive": pos_total}

    def query_ops_queue(
        self,
        run_id: str,
        grade: str | None = None,
        limit: int = 200,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM ops_queue_rows WHERE run_id=? AND case_id=?"
        params: list[Any] = [run_id, CASE_PRIMARY_AUX]
        if grade:
            sql += " AND ops_grade=?"
            params.append(grade)
        sql += " ORDER BY COALESCE(priority, 99), score_primary DESC LIMIT ?"
        params.append(limit)
        with connect(self.cfg) as conn:
            rows = conn.execute(sql, params).fetchall()
        return pd.DataFrame([dict(r) for r in rows])


def _to_float(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _row_get(row: pd.Series, *names: str) -> Any:
    for n in names:
        if n in row.index and pd.notna(row[n]):
            return row[n]
    return None


def _spec_by_id(case_id: str) -> OpsPairSpec | None:
    for s in OPS_PAIR_SPECS:
        if s.case_id == case_id:
            return s
    return None


def _spec_for_queue(queue_df: pd.DataFrame) -> OpsPairSpec:
    from src.scoring.ops_capture import CASE_ID_COL

    if CASE_ID_COL in queue_df.columns and len(queue_df):
        cid = str(queue_df[CASE_ID_COL].iloc[0])
        spec = _spec_by_id(cid)
        if spec:
            return spec
    return OPS_PAIR_SPECS[0]


def _band_counts_to_matrix(
    rows: list[Any], spec: OpsPairSpec | None = None
) -> pd.DataFrame:
    if spec is None:
        mat = empty_band_matrix()
        row_labels, col_labels = PRIMARY_LABELS, AUX_LABELS
    else:
        from src.scoring.ops_capture import empty_band_matrix_for

        mat = empty_band_matrix_for(spec)
        row_labels, col_labels = spec.row_labels, spec.col_labels

    col_key = "grade_col"
    for r in rows:
        rd = dict(r) if hasattr(r, "keys") else {}
        if not rd and hasattr(r, "__getitem__"):
            rd = {"ops_grade": r[0], "grade_col": r[1], "cnt": r[2]}
        p = str(rd.get("ops_grade") or "")
        a = str(rd.get(col_key) or rd.get("grade_aux") or "")
        c = int(rd.get("cnt") or 0)
        if p in row_labels and a in col_labels:
            mat.loc[p, a] = c
    return mat.astype(int)
