"""App metadata for frontend."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.constants import ALGO_LABELS, METRIC_HELP, PREVIEW_OPTIONS
from api.deps import get_cfg

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/meta")
def meta(cfg=Depends(get_cfg)) -> dict:
    return {
        "algo_labels": ALGO_LABELS,
        "algorithms": cfg.get("algorithms", []),
        "metric_help": METRIC_HELP,
        "preview_options": list(PREVIEW_OPTIONS),
        "train_steps": [
            {"id": s["id"], "label": s["label"]}
            for s in __import__(
                "src.pipeline.runner", fromlist=["TRAIN_PIPELINE_STEPS"]
            ).TRAIN_PIPELINE_STEPS
        ],
    }
