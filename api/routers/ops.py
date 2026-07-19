"""Target capture / ops queue."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.constants import PREVIEW_OPTIONS
from api.deps import get_cfg, get_repo
from api.serializers import df_to_records, matrix_to_payload
from api.services.metrics import format_ops_summary, sort_ops_summary_priority
from src.scoring.ops_queue import BAND_HELP, PRIMARY_LABELS

router = APIRouter(tags=["ops"])


@router.get("/api/runs/{run_id}/ops-queue")
def ops_queue(
    run_id: str,
    grade: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
) -> dict:
    if limit not in PREVIEW_OPTIONS:
        limit = min(PREVIEW_OPTIONS, key=lambda x: abs(x - limit))

    test_block: dict = {"empty": True}
    summary_rows: list = []
    preview_rows: list = []

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

            summary = sort_ops_summary_priority(repo.ops_queue_summary(run_id))
            summary_fmt = format_ops_summary(summary)
            summary_rows = df_to_records(summary_fmt)

            g = None if not grade or grade == "(전체)" else grade
            preview = repo.query_ops_queue(run_id, grade=g, limit=limit)
            preview_rows = df_to_records(preview)
    except Exception:  # noqa: BLE001
        pass

    return {
        "run_id": run_id,
        "band_help": BAND_HELP,
        "primary_labels": list(PRIMARY_LABELS),
        "preview_options": list(PREVIEW_OPTIONS),
        "test_matrices": test_block,
        "summary": summary_rows,
        "preview": preview_rows,
        "preview_limit": limit,
    }
