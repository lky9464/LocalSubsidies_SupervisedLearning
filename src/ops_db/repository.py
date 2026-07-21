"""운영 DB 읽기/쓰기 (집계·메타·타겟 포착/점검 우선순위 조회용)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pandas as pd

from src.ops_db.db import connect, init_db
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

    def save_ranking(self, run_id: str, ranking: list[dict[str, Any]]) -> None:
        self.ensure_run(run_id)
        with connect(self.cfg) as conn:
            conn.execute("DELETE FROM model_ranking WHERE run_id=?", (run_id,))
            for row in ranking:
                conn.execute(
                    """
                    INSERT INTO model_ranking(
                        run_id, rank, algo, role, pr_auc, roc_auc, top1_lift, f1
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                    ),
                )
            conn.commit()

    def get_ranking(self, run_id: str) -> list[dict[str, Any]]:
        with connect(self.cfg) as conn:
            rows = conn.execute(
                "SELECT * FROM model_ranking WHERE run_id=? ORDER BY rank",
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

    def replace_ops_queue(self, run_id: str, queue_df: pd.DataFrame) -> int:
        """주·보 구간·우선순위 운영 컬럼만 적재 (기여도 TOP 등 제외)."""
        self.ensure_run(run_id)
        keys = self.cfg.get("key_columns", ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"])
        col_ym, col_biz, col_inst = keys[0], keys[1], keys[2]

        def _get(row: pd.Series, *names: str) -> Any:
            for n in names:
                if n in row.index and pd.notna(row[n]):
                    return row[n]
            return None

        rows = []
        for _, row in queue_df.iterrows():
            pri = _get(row, PRIORITY_COL)
            try:
                pri_i = int(pri) if pri is not None and str(pri) != "" else None
            except (TypeError, ValueError):
                pri_i = None
            rows.append(
                (
                    run_id,
                    str(_get(row, col_ym) or ""),
                    str(_get(row, col_biz) or ""),
                    str(_get(row, col_inst) or ""),
                    str(_get(row, "수행사업명칭(PFM_BIZ_NM)") or ""),
                    str(_get(row, "기관명(INST_NM)") or ""),
                    str(_get(row, "사업비보조금금액(BIZCT_SBAT_AMT)") or ""),
                    str(_get(row, "사업비자부담금액(BIZCT_PYHWY_AMT)") or ""),
                    _to_float(_get(row, RF_SCORE_COL)),
                    _to_float(_get(row, CB_SCORE_COL)),
                    str(_get(row, GRADE_COL) or ""),
                    str(_get(row, CELL_COL) or ""),
                    str(_get(row, CB_GRADE_COL) or ""),
                    pri_i,
                    str(_get(row, PRED_COL) if PRED_COL in row.index else ""),
                    str(_get(row, ACTUAL_COL) if ACTUAL_COL in row.index else ""),
                )
            )

        with connect(self.cfg) as conn:
            conn.execute("DELETE FROM ops_queue_rows WHERE run_id=?", (run_id,))
            conn.executemany(
                """
                INSERT INTO ops_queue_rows(
                    run_id, crtr_ym, pfm_biz_id, inst_id, biz_nm, inst_nm,
                    sbat_amt, pyhwy_amt, score_primary, score_aux,
                    ops_grade, cross_check, grade_aux, priority,
                    pred_label, actual_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
        return len(rows)

    def ops_queue_summary(self, run_id: str) -> pd.DataFrame:
        """주×보 조합별 건수 (우선순위 순)."""
        with connect(self.cfg) as conn:
            rows = conn.execute(
                """
                SELECT ops_grade AS primary_band,
                       grade_aux AS aux_band,
                       cross_check AS cell,
                       MIN(priority) AS priority,
                       COUNT(*) AS cnt
                FROM ops_queue_rows
                WHERE run_id=?
                GROUP BY ops_grade, grade_aux, cross_check
                ORDER BY COALESCE(MIN(priority), 99), ops_grade, grade_aux
                """,
                (run_id,),
            ).fetchall()
        return pd.DataFrame([dict(r) for r in rows])

    def ops_queue_matrices(
        self, run_id: str
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, int]]:
        """
        Test 타겟 포착 4×4: (전체 건수, 실제 타겟=1 건수, 메타).
        행단위 raw는 반환하지 않고 집계만 사용.
        """
        with connect(self.cfg) as conn:
            all_rows = conn.execute(
                """
                SELECT ops_grade, grade_aux, COUNT(*) AS cnt
                FROM ops_queue_rows
                WHERE run_id=?
                GROUP BY ops_grade, grade_aux
                """,
                (run_id,),
            ).fetchall()
            pos_rows = conn.execute(
                """
                SELECT ops_grade, grade_aux, COUNT(*) AS cnt
                FROM ops_queue_rows
                WHERE run_id=?
                  AND LOWER(TRIM(COALESCE(actual_label, '')))
                      IN ('1', '1.0', 'y', 'yes', 'true', 't')
                GROUP BY ops_grade, grade_aux
                """,
                (run_id,),
            ).fetchall()

        matrix_all = _band_counts_to_matrix(all_rows)
        matrix_pos = _band_counts_to_matrix(pos_rows)
        total = int(matrix_all.to_numpy().sum())
        pos_total = int(matrix_pos.to_numpy().sum())
        return matrix_all, matrix_pos, {"total": total, "positive": pos_total}

    def query_ops_queue(
        self,
        run_id: str,
        grade: str | None = None,
        limit: int = 200,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM ops_queue_rows WHERE run_id=?"
        params: list[Any] = [run_id]
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


def _band_counts_to_matrix(rows: list[Any]) -> pd.DataFrame:
    mat = empty_band_matrix()
    for r in rows:
        p = str(r["ops_grade"] if hasattr(r, "keys") else r[0] or "")
        a = str(r["grade_aux"] if hasattr(r, "keys") else r[1] or "")
        c = int(r["cnt"] if hasattr(r, "keys") else r[2] or 0)
        if p in PRIMARY_LABELS and a in AUX_LABELS:
            mat.loc[p, a] = c
    return mat.astype(int)
