"""App metadata for frontend."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.constants import METRIC_HELP, PREVIEW_OPTIONS
from api.deps import get_cfg
from src.models.registry import build_algo_labels_map, list_algo_ids, registry_payload

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/meta")
def meta(cfg=Depends(get_cfg)) -> dict:
    labels = build_algo_labels_map(cfg)
    algos = list_algo_ids(cfg)
    return {
        "algo_labels": labels,
        "algorithms": algos,
        "algorithm_registry": registry_payload(cfg),
        "metric_help": METRIC_HELP,
        "preview_options": list(PREVIEW_OPTIONS),
        "train_steps": [
            {"id": s["id"], "label": s["label"]}
            for s in __import__(
                "src.pipeline.runner", fromlist=["TRAIN_PIPELINE_STEPS"]
            ).TRAIN_PIPELINE_STEPS
        ],
    }
