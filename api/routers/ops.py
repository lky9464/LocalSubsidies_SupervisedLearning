"""Target capture / ops queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.deps import get_cfg
from api.services.ops_capture import build_ops_case_payload, build_ops_queue_payload

router = APIRouter(tags=["ops"])


@router.get("/api/runs/{run_id}/ops-queue")
def ops_queue(
    run_id: str,
    full: bool = Query(
        False,
        description="True면 3케이스 매트릭스 일괄(레거시). 기본은 메타만(지연 로드).",
    ),
    cfg=Depends(get_cfg),
) -> dict:
    try:
        return build_ops_queue_payload(cfg, run_id, include_matrices=full)
    except Exception:  # noqa: BLE001
        return {
            "run_id": run_id,
            "band_help": {},
            "roles": {},
            "cases": [],
            "test_matrices": {"empty": True},
            "lazy": True,
        }


@router.get("/api/runs/{run_id}/ops-queue/cases/{case_id}")
def ops_queue_case(
    run_id: str,
    case_id: str,
    cfg=Depends(get_cfg),
) -> dict:
    try:
        return build_ops_case_payload(cfg, run_id, case_id)
    except Exception:  # noqa: BLE001
        return {
            "id": case_id,
            "available": False,
            "reason": "타겟 포착 데이터를 불러오지 못했습니다.",
            "loaded": True,
        }
