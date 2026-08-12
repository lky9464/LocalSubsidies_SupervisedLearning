"""Inference 점검 우선순위 — 3케이스(PK·엔티티) pair queue (Test ops_capture 패턴)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.io.config import resolve_data_path
from src.ops_db.repository import OpsRepository
from src.scoring.inference_helpers import inference_score_path
from src.scoring.ops_capture import (
    CASE_AUX_REF,
    CASE_PRIMARY_AUX,
    CASE_PRIMARY_REF,
    OPS_PAIR_SPECS,
    OpsPairSpec,
    aggregate_entity_queue,
    build_ops_pair_queue,
    parse_entity_keys,
    summarize_matrix_for,
    summarize_ops_pair,
)
from src.scoring.ops_queue import sanitize_for_excel


def inference_capture_pk_paths(
    cfg: dict[str, Any], *, run_id: str | None = None
) -> tuple[Path, Path]:
    out_dir = resolve_data_path(cfg, "algorithms", run_id=run_id) / "operations"
    return out_dir / "ops_queue_inference_pk.csv", out_dir / "ops_queue_inference_pk.xlsx"


def inference_capture_entity_paths(
    cfg: dict[str, Any], *, run_id: str | None = None
) -> tuple[Path, Path]:
    out_dir = resolve_data_path(cfg, "algorithms", run_id=run_id) / "operations"
    return (
        out_dir / "ops_queue_inference_entity.csv",
        out_dir / "ops_queue_inference_entity.xlsx",
    )


def _trained_algos_for_run(cfg: dict[str, Any], run_id: str) -> list[str]:
    from src.io.config import resolve_algo_dir
    from src.pipeline.run_config import load_run_config

    if not run_id:
        return []
    repo = OpsRepository(cfg)
    if not repo.step_succeeded(run_id, "train"):
        return []
    run_cfg = load_run_config(cfg, run_id)
    configured = [str(a) for a in (run_cfg.get("algorithms") or [])]
    trained: list[str] = []
    for algo in configured:
        model_path = resolve_algo_dir(cfg, algo, run_id=run_id) / "model.joblib"
        if model_path.is_file():
            trained.append(algo)
    return trained


def allowed_inference_role_algos(cfg: dict[str, Any], run_id: str) -> list[str]:
    """08 순위 주·보·참 중 이 Run에서 학습된 algo_id (추론 선택 허용 목록)."""
    if not run_id:
        return []
    repo = OpsRepository(cfg)
    roles = repo.get_roles(run_id)
    trained = set(_trained_algos_for_run(cfg, run_id))
    out: list[str] = []
    for key in ("primary", "aux", "reference"):
        algo = roles.get(key)
        if algo and algo in trained and algo not in out:
            out.append(str(algo))
    return out


def _load_inference_score(path: Path, encoding: str) -> pd.DataFrame | None:
    if not path.is_file():
        return None
    return pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False)


def _case_inference_dfs(
    spec: OpsPairSpec,
    scores: dict[str, pd.DataFrame | None],
    roles: dict[str, str | None],
    infer_algos: list[str],
) -> tuple[pd.DataFrame | None, pd.DataFrame | None, str | None]:
    primary = roles.get("primary")
    aux = roles.get("aux")
    reference = roles.get("reference")
    infer_set = set(infer_algos)

    if spec.case_id == CASE_PRIMARY_AUX:
        if not primary or not aux:
            return None, None, "주·보 모델(08 순위) 없음"
        if primary not in infer_set or aux not in infer_set:
            return None, None, "주·보 알고리즘 추론 필요"
        row_df, col_df = scores.get(primary), scores.get(aux)
        if row_df is None:
            return None, None, f"주 모델 inference 점수 없음: {primary}"
        if col_df is None:
            return None, None, f"보조 모델 inference 점수 없음: {aux}"
        return row_df, col_df, None

    if spec.case_id == CASE_PRIMARY_REF:
        if not reference:
            return None, None, "참조 모델(reference) 없음 — 08 순위 3위 필요"
        if primary not in infer_set or reference not in infer_set:
            return None, None, "주·참 알고리즘 추론 필요"
        row_df, col_df = scores.get(primary), scores.get(reference)
        if row_df is None:
            return None, None, f"주 모델 inference 점수 없음: {primary}"
        if col_df is None:
            return None, None, f"참조 모델 inference 점수 없음: {reference}"
        return row_df, col_df, None

    if spec.case_id == CASE_AUX_REF:
        if not reference:
            return None, None, "참조 모델(reference) 없음 — 08 순위 3위 필요"
        if aux not in infer_set or reference not in infer_set:
            return None, None, "보·참 알고리즘 추론 필요"
        row_df, col_df = scores.get(aux), scores.get(reference)
        if row_df is None:
            return None, None, f"보조 모델 inference 점수 없음: {aux}"
        if col_df is None:
            return None, None, f"참조 모델 inference 점수 없음: {reference}"
        return row_df, col_df, None

    return None, None, "unknown case"


def build_inference_capture_queues(
    cfg: dict[str, Any],
    run_id: str,
    infer_algos: list[str],
) -> tuple[list[pd.DataFrame], list[pd.DataFrame], dict[str, pd.DataFrame], dict[str, pd.DataFrame]]:
    """3케이스 PK·entity queue 생성. infer_algos = 이번 추론에 실행한 algo (08 역할 subset)."""
    encoding = cfg.get("encoding", "EUC-KR")
    ops_cfg = dict(cfg.get("ops_queue") or {})
    keys = list(cfg.get("key_columns") or [])
    entity_keys = parse_entity_keys(cfg)

    repo = OpsRepository(cfg)
    roles = repo.get_roles(run_id)

    score_cache: dict[str, pd.DataFrame | None] = {}
    for algo in {roles.get("primary"), roles.get("aux"), roles.get("reference")}:
        if not algo:
            continue
        if algo not in score_cache:
            path = inference_score_path(cfg, algo, run_id=run_id)
            score_cache[str(algo)] = _load_inference_score(path, encoding)

    pk_queues: list[pd.DataFrame] = []
    entity_queues: list[pd.DataFrame] = []
    pk_by_case: dict[str, pd.DataFrame] = {}
    entity_by_case: dict[str, pd.DataFrame] = {}

    for spec in OPS_PAIR_SPECS:
        row_df, col_df, err = _case_inference_dfs(spec, score_cache, roles, infer_algos)
        if err or row_df is None or col_df is None:
            continue
        pk_q = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
        ent_q = aggregate_entity_queue(
            pk_q, entity_keys, ops_cfg, spec, preserve_blank_actual=True
        )
        pk_queues.append(pk_q)
        entity_queues.append(ent_q)
        pk_by_case[spec.case_id] = pk_q
        entity_by_case[spec.case_id] = ent_q

    return pk_queues, entity_queues, pk_by_case, entity_by_case


def write_inference_capture_workbook(
    pk_by_case: dict[str, pd.DataFrame],
    entity_by_case: dict[str, pd.DataFrame],
    out_path: Path,
    *,
    unit: str,
) -> None:
    """추론용 Excel — (A-1)/(B-1)만 (양성 분포 시트 없음)."""
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        all_frames: list[pd.DataFrame] = []
        for spec in OPS_PAIR_SPECS:
            q = pk_by_case.get(spec.case_id) if unit == "pk" else entity_by_case.get(spec.case_id)
            if q is None or q.empty:
                continue
            clean = sanitize_for_excel(q)
            all_frames.append(clean)
            prefix = spec.case_id
            clean.to_excel(writer, sheet_name=f"{prefix}_전체"[:31], index=False)
            summarize_ops_pair(clean, spec).to_excel(
                writer, sheet_name=f"{prefix}_요약"[:31], index=False
            )
            summarize_matrix_for(clean, spec).to_excel(
                writer, sheet_name=f"{prefix}_A1"[:31], index=False
            )

        if all_frames:
            pd.concat(all_frames, ignore_index=True).to_excel(
                writer, sheet_name="전체", index=False
            )


def export_inference_capture(
    cfg: dict[str, Any],
    run_id: str,
    infer_algos: list[str],
    *,
    repo: OpsRepository | None = None,
) -> tuple[Path, Path, Path, Path, int, int]:
    """PK/entity CSV·Excel 저장 + ops.sqlite inference 테이블 적재."""
    pk_queues, entity_queues, pk_by_case, entity_by_case = build_inference_capture_queues(
        cfg, run_id, infer_algos
    )
    if not pk_queues:
        raise FileNotFoundError(
            "추론 점검 우선순위표를 만들 수 없습니다 — "
            "주·보 inference 점수와 08 순위 역할을 확인하세요."
        )

    encoding = cfg.get("encoding", "EUC-KR")
    pk_csv, pk_xlsx = inference_capture_pk_paths(cfg, run_id=run_id)
    ent_csv, ent_xlsx = inference_capture_entity_paths(cfg, run_id=run_id)
    pk_csv.parent.mkdir(parents=True, exist_ok=True)

    pd.concat(pk_queues, ignore_index=True).to_csv(pk_csv, index=False, encoding=encoding)
    write_inference_capture_workbook(pk_by_case, entity_by_case, pk_xlsx, unit="pk")

    if entity_queues:
        pd.concat(entity_queues, ignore_index=True).to_csv(
            ent_csv, index=False, encoding=encoding
        )
        write_inference_capture_workbook(pk_by_case, entity_by_case, ent_xlsx, unit="entity")

    repo = repo or OpsRepository(cfg)
    repo.ensure_run(run_id, note="inference_capture")
    pk_n, ent_n = repo.replace_inference_capture(run_id, pk_queues, entity_queues)

    return pk_csv, pk_xlsx, ent_csv, ent_xlsx, pk_n, ent_n
