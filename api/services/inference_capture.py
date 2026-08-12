"""Inference 점검 우선순위 API 페이로드 (Test ops_capture 미러)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.serializers import df_to_records, matrix_to_payload
from api.services.metrics import sort_ops_summary_priority
from src.models.registry import build_algo_labels_map, resolve_algo_label
from src.ops_db.repository import OpsRepository
from src.scoring.inference_capture import allowed_inference_role_algos
from src.scoring.inference_helpers import inference_algorithms_for_run, run_has_inference_step
from src.scoring.ops_capture import (
    BAND_HELP_REF,
    CASE_AUX_REF,
    CASE_PRIMARY_AUX,
    CASE_PRIMARY_REF,
    OPS_PAIR_SPECS,
)
from src.scoring.ops_queue import BAND_HELP


def _inference_matrix_block(
    repo: OpsRepository, run_id: str, case_id: str, unit: str
) -> dict[str, Any]:
    mat_all, _, meta = repo.inference_capture_matrices(run_id, case_id, unit=unit)
    if meta.get("total", 0) <= 0:
        return {
            "all": None,
            "meta": meta,
        }
    return {
        "all": matrix_to_payload(mat_all),
        "meta": meta,
    }


def _role_payload(cfg: dict, run_id: str, repo: OpsRepository) -> dict[str, Any]:
    roles = repo.get_roles(run_id)
    labels_map = build_algo_labels_map(cfg)
    return {
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


def _case_unavailable_reason(
    case_id: str,
    roles: dict[str, str | None],
    infer_algos: list[str],
) -> str | None:
    infer_set = set(infer_algos)
    primary, aux, reference = roles.get("primary"), roles.get("aux"), roles.get("reference")

    if case_id == CASE_PRIMARY_AUX:
        if not primary or not aux:
            return "주·보 모델(08 순위) 없음"
        missing = [a for a in (primary, aux) if a not in infer_set]
        if missing:
            return "주·보 알고리즘 추론 필요"
        return None

    if case_id in (CASE_PRIMARY_REF, CASE_AUX_REF):
        if not reference:
            return "참조 모델(reference) 없음 — 08 순위 3위 필요"
        if case_id == CASE_PRIMARY_REF:
            missing = [a for a in (primary, reference) if a and a not in infer_set]
            if primary not in infer_set or reference not in infer_set:
                return "주·참 알고리즘 추론 필요"
        else:
            if aux not in infer_set or reference not in infer_set:
                return "보·참 알고리즘 추론 필요"
        return None

    return f"알 수 없는 case_id: {case_id}"


def build_inference_queue_payload(
    cfg: dict,
    run_id: str,
    *,
    include_matrices: bool = False,
) -> dict[str, Any]:
    if not run_has_inference_step(cfg, run_id):
        return {
            "run_id": run_id,
            "empty": True,
            "run_inference_missing": True,
            "band_help": {},
            "roles": {},
            "cases": [],
            "lazy": True,
        }

    repo = OpsRepository(cfg)
    role_payload = _role_payload(cfg, run_id, repo)
    band_help = {**BAND_HELP, **BAND_HELP_REF}
    infer_algos = inference_algorithms_for_run(cfg, run_id)

    cases: list[dict[str, Any]] = []
    for spec in OPS_PAIR_SPECS:
        case: dict[str, Any] = {
            "id": spec.case_id,
            "title": spec.title,
            "row_axis": spec.row_prefix,
            "col_axis": spec.col_prefix,
            "available": True,
            "reason": None,
            "loaded": False,
        }

        reason = _case_unavailable_reason(spec.case_id, role_payload, infer_algos)
        if reason:
            case["available"] = False
            case["reason"] = reason
            cases.append(case)
            continue

        n = repo.inference_capture_row_count(run_id, spec.case_id)
        if n <= 0:
            case["available"] = False
            case["reason"] = "11 단계 산출물 없음 — 추론을 다시 실행하세요."
            cases.append(case)
            continue

        if include_matrices:
            detail = build_inference_case_payload(cfg, run_id, spec.case_id, repo=repo)
            case.update(detail)
            case["loaded"] = True
        cases.append(case)

    return {
        "run_id": run_id,
        "empty": not any(c.get("available") for c in cases),
        "band_help": band_help,
        "roles": role_payload,
        "cases": cases,
        "lazy": not include_matrices,
    }


def build_inference_case_payload(
    cfg: dict,
    run_id: str,
    case_id: str,
    *,
    repo: OpsRepository | None = None,
) -> dict[str, Any]:
    repo = repo or OpsRepository(cfg)
    roles = repo.get_roles(run_id)
    role_payload = _role_payload(cfg, run_id, repo)
    infer_algos = inference_algorithms_for_run(cfg, run_id)
    spec = next((s for s in OPS_PAIR_SPECS if s.case_id == case_id), None)
    if spec is None:
        return {
            "id": case_id,
            "available": False,
            "reason": f"알 수 없는 case_id: {case_id}",
            "loaded": True,
        }

    reason = _case_unavailable_reason(case_id, roles, infer_algos)
    if reason:
        return {
            "id": case_id,
            "title": spec.title,
            "row_axis": spec.row_prefix,
            "col_axis": spec.col_prefix,
            "available": False,
            "reason": reason,
            "loaded": True,
        }

    pk_block = _inference_matrix_block(repo, run_id, case_id, "pk")
    if pk_block["meta"].get("total", 0) <= 0:
        return {
            "id": case_id,
            "title": spec.title,
            "row_axis": spec.row_prefix,
            "col_axis": spec.col_prefix,
            "available": False,
            "reason": "11 단계 산출물 없음 — 추론을 다시 실행하세요.",
            "loaded": True,
        }

    ent_block = _inference_matrix_block(repo, run_id, case_id, "entity")
    summary_df = sort_ops_summary_priority(repo.inference_capture_summary(run_id, case_id))
    summary_fmt = _format_inference_summary(summary_df, spec.row_prefix, spec.col_prefix)

    return {
        "id": case_id,
        "title": spec.title,
        "row_axis": spec.row_prefix,
        "col_axis": spec.col_prefix,
        "available": True,
        "reason": None,
        "loaded": True,
        "matrices": {"pk": pk_block, "entity": ent_block},
        "summary": df_to_records(summary_fmt),
    }


def _format_inference_summary(
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


def validate_inference_algo_selection(cfg: dict, run_id: str, selected: list[str]) -> str | None:
    """08 주·보·참 허용 목록 밖 algo면 오류 메시지."""
    allowed = set(allowed_inference_role_algos(cfg, run_id))
    if not allowed:
        return "08 순위 주·보·참 모델이 이 Run에서 학습되지 않았습니다."
    bad = [a for a in selected if a not in allowed]
    if bad:
        return f"추론은 08 순위 주·보·참 모델만 선택할 수 있습니다: {', '.join(bad)}"
    return None
