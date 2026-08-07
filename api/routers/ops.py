"""Target capture / ops queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_cfg
from api.services.ops_capture import build_ops_queue_payload

router = APIRouter(tags=["ops"])


@router.get("/api/runs/{run_id}/ops-queue")
def ops_queue(
    run_id: str,
    cfg=Depends(get_cfg),
) -> dict:
    try:
        return build_ops_queue_payload(cfg, run_id)
    except Exception:  # noqa: BLE001
        return {
            "run_id": run_id,
            "band_help": {},
            "roles": {},
            "cases": [],
            "test_matrices": {"empty": True},
        }
