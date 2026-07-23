"""Dashboard aggregates."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.constants import ALGO_LABELS
from api.deps import get_cfg, get_job_manager, get_repo
from api.serializers import df_to_records, matrix_to_payload
from api.services.inference import dashboard_inference_block
from api.services.metrics import build_compare_frame
from src.scoring.ops_queue import summarize_matrix

router = APIRouter(tags=["dashboard"])


@router.get("/api/runs/{run_id}/dashboard")
def dashboard(run_id: str, cfg=Depends(get_cfg), repo=Depends(get_repo), mgr=Depends(get_job_manager)) -> dict:
    ranking = repo.get_ranking(run_id)
    ranking_empty = len(ranking) == 0
    compare = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id=run_id)
    primary, aux = repo.get_primary_aux(run_id)

    test_block: dict = {"empty": True}
    try:
        mat_all, mat_pos, meta = repo.ops_queue_matrices(run_id)
        if meta.get("total", 0) > 0:
            pos = int(meta.get("positive", 0))
            pos_in_abc = 0
            if pos > 0:
                for p in ("주A", "주B", "주C"):
                    if p in mat_pos.index:
                        pos_in_abc += int(mat_pos.loc[p].sum())
            test_block = {
                "empty": False,
                "meta": meta,
                "matrix_all": matrix_to_payload(mat_all),
                "matrix_pos": matrix_to_payload(mat_pos),
                "positive_in_abc_pct": round(pos_in_abc / pos * 100, 1) if pos else None,
            }
    except Exception:  # noqa: BLE001
        pass

    infer_block: dict = {"empty": True}
    try:
        payload = dashboard_inference_block(cfg, run_id)
        if not payload.get("empty"):
            infer_block = {
                "empty": False,
                "total": payload.get("total", 0),
                "primary": payload.get("primary"),
                "aux": payload.get("aux"),
                "primary_label": ALGO_LABELS.get(payload.get("primary", ""), payload.get("primary")),
                "aux_label": ALGO_LABELS.get(payload.get("aux", ""), payload.get("aux")),
                "matrix": payload.get("matrix"),
            }
        else:
            infer_block = {
                "empty": True,
                "run_inference_missing": bool(payload.get("run_inference_missing")),
                "primary": payload.get("primary"),
                "aux": payload.get("aux"),
            }
    except Exception:  # noqa: BLE001
        pass

    job = mgr.get_active_job(mutate=False)
    runs = repo.list_runs(5)

    return {
        "run_id": run_id,
        "ranking_empty": ranking_empty,
        "ranking": df_to_records(compare),
        "primary": primary,
        "aux": aux,
        "primary_label": ALGO_LABELS.get(primary, primary),
        "aux_label": ALGO_LABELS.get(aux, aux),
        "test_matrices": test_block,
        "inference": infer_block,
        "job_status": (job or {}).get("status"),
        "recent_runs_count": len(runs),
    }
