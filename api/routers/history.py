"""Run history."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_cfg, get_repo
from api.serializers import df_to_records, matrix_to_payload
from api.services.metrics import build_compare_frame

router = APIRouter(tags=["history"])


@router.get("/api/runs/{run_id}/history")
def run_history(run_id: str, cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    steps = repo.list_steps(run_id)
    ranking = repo.get_ranking(run_id)
    compare = build_compare_frame(cfg, ranking, allow_global_fallback=False)

    test_block: dict = {"empty": True}
    try:
        mat_all, mat_pos, meta = repo.ops_queue_matrices(run_id)
        if meta.get("total", 0) > 0:
            test_block = {
                "empty": False,
                "meta": meta,
                "matrix_all": matrix_to_payload(mat_all),
                "matrix_pos": matrix_to_payload(mat_pos),
            }
    except Exception:  # noqa: BLE001
        pass

    return {
        "run_id": run_id,
        "steps": steps,
        "ranking": df_to_records(compare),
        "test_matrices": test_block,
    }
