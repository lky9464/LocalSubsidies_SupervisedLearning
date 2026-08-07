"""타겟 포착 분포 API 페이로드."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.serializers import df_to_records, matrix_to_payload
from api.services.metrics import sort_ops_summary_priority
from src.models.registry import build_algo_labels_map, resolve_algo_label
from src.ops_db.repository import OpsRepository
from src.scoring.ops_capture import (
    BAND_HELP_REF,
    CASE_AUX_REF,
    CASE_PRIMARY_AUX,
    CASE_PRIMARY_REF,
    OPS_PAIR_SPECS,
    positive_in_row_abc_pct,
)
from src.scoring.ops_queue import BAND_HELP


def _matrix_block(
    repo: OpsRepository, run_id: str, case_id: str, unit: str
) -> dict[str, Any]:
    mat_all, mat_pos, meta = repo.ops_capture_matrices(run_id, case_id, unit=unit)
    if meta.get("total", 0) <= 0:
        return {
            "all": None,
            "positive": None,
            "meta": meta,
            "positive_in_abc_pct": None,
        }
    spec = next((s for s in OPS_PAIR_SPECS if s.case_id == case_id), None)
    pct = None
    if spec and meta.get("positive", 0):
        pct = positive_in_row_abc_pct(mat_pos, spec)
    return {
        "all": matrix_to_payload(mat_all),
        "positive": matrix_to_payload(mat_pos),
        "meta": meta,
        "positive_in_abc_pct": pct,
    }


def build_ops_queue_payload(cfg: dict, run_id: str) -> dict[str, Any]:
    repo = OpsRepository(cfg)
    roles = repo.get_roles(run_id)
    labels_map = build_algo_labels_map(cfg)

    role_payload = {
        **roles,
        "primary_label": resolve_algo_label(roles["primary"] or "", labels_map)
        if roles.get("primary")
        else None,
        "aux_label": resolve_algo_label(roles["aux"] or "", labels_map)
        if roles.get("aux")
        else None,
        "reference_label": resolve_algo_label(roles["reference"] or "", labels_map)
        if roles.get("reference")
        else None,
    }

    band_help = {**BAND_HELP, **BAND_HELP_REF}

    cases: list[dict[str, Any]] = []
    for spec in OPS_PAIR_SPECS:
        case: dict[str, Any] = {
            "id": spec.case_id,
            "title": spec.title,
            "row_axis": spec.row_prefix,
            "col_axis": spec.col_prefix,
            "available": True,
            "reason": None,
        }

        needs_ref = spec.case_id in (CASE_PRIMARY_REF, CASE_AUX_REF)
        if needs_ref and not roles.get("reference"):
            case["available"] = False
            case["reason"] = (
                "참조 모델(reference) 없음 — 08 순위 3위 또는 해당 algo Test 점수 필요"
            )
            cases.append(case)
            continue

        pk_block = _matrix_block(repo, run_id, spec.case_id, "pk")
        ent_block = _matrix_block(repo, run_id, spec.case_id, "entity")
        if pk_block["meta"].get("total", 0) <= 0:
            case["available"] = False
            case["reason"] = "10 단계 산출물 없음 — 타겟 포착 분포를 실행하세요."
            cases.append(case)
            continue

        summary_df = sort_ops_summary_priority(
            repo.ops_capture_summary(run_id, spec.case_id)
        )
        summary_fmt = format_capture_summary(summary_df, spec.row_prefix, spec.col_prefix)

        case["matrices"] = {"pk": pk_block, "entity": ent_block}
        case["summary"] = df_to_records(summary_fmt)
        case["positive_in_abc_pct"] = pk_block.get("positive_in_abc_pct")
        cases.append(case)

    primary_case = next((c for c in cases if c["id"] == CASE_PRIMARY_AUX), None)
    test_matrices: dict[str, Any] = {"empty": True}
    if primary_case and primary_case.get("available") and primary_case.get("matrices"):
        pk = primary_case["matrices"]["pk"]
        test_matrices = {
            "empty": False,
            "meta": pk["meta"],
            "matrix_all": pk["all"],
            "matrix_pos": pk["positive"],
            "positive_in_abc_pct": pk.get("positive_in_abc_pct"),
        }

    return {
        "run_id": run_id,
        "band_help": band_help,
        "roles": role_payload,
        "cases": cases,
        "test_matrices": test_matrices,
    }


def format_capture_summary(
    summary: pd.DataFrame, row_prefix: str, col_prefix: str
) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    rename = {
        "cell": "조합",
        "priority": "우선순위",
        "count_pk": "건수(PK 기준)",
        "count_entity": "건수(엔티티 기준)",
        "row_band": f"{row_prefix}등급",
        "col_band": f"{col_prefix}등급",
    }
    return out.rename(columns={k: v for k, v in rename.items() if k in out.columns})
