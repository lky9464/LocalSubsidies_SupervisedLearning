"""Model comparison."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.constants import METRIC_HELP
from api.deps import get_cfg, get_repo
from api.serializers import df_to_records
from api.services.metrics import build_compare_frame, radar_chart_data
from api.services.model_insights import build_role_insight_panels, role_algos_from_ranking
from src.io.config import resolve_data_path
from src.models.registry import build_algo_labels_map, resolve_algo_label
from src.pipeline.ranking import load_ranking_artifact

router = APIRouter(tags=["models"])


@router.get("/api/runs/{run_id}/models")
def models_compare(
    run_id: str,
    metrics: str | None = Query(None),
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
) -> dict:
    ranking = repo.get_ranking(run_id)
    ranking_empty = len(ranking) == 0
    compare = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id=run_id)
    primary, aux = repo.get_primary_aux(run_id)
    role_map = role_algos_from_ranking(ranking)
    reference = role_map.get("reference")

    metric_list = [m.strip() for m in metrics.split(",")] if metrics else None
    radar = radar_chart_data(compare, metric_list)

    rank_meta: dict[str, str] = {}
    rank_path = resolve_data_path(cfg, "algorithms", run_id=run_id) / "operations" / "model_ranking.json"
    _, rank_meta = load_ranking_artifact(rank_path)

    labels_map = build_algo_labels_map(cfg)
    top_n = int(cfg.get("feature_importance", {}).get("top_n", 10))
    insights = build_role_insight_panels(
        cfg,
        ranking,
        run_id=run_id,
        labels_map=labels_map,
        top_n=top_n,
    )

    return {
        "run_id": run_id,
        "empty": ranking_empty,
        "ranking": df_to_records(compare),
        "ranking_confidence": rank_meta.get("ranking_confidence"),
        "ranking_note": rank_meta.get("ranking_note"),
        "primary": primary,
        "aux": aux,
        "reference": reference,
        "primary_label": resolve_algo_label(primary, labels_map) if primary else primary,
        "aux_label": resolve_algo_label(aux, labels_map) if aux else aux,
        "reference_label": (
            resolve_algo_label(reference, labels_map) if reference else None
        ),
        "metric_help": METRIC_HELP,
        "radar_metrics_available": [
            "PR-AUC",
            "상위1%리프트",
            "상위1%양성비중",
            "상위1%양성포착",
            "상위5%리프트",
            "상위5%양성비중",
            "상위5%양성포착",
            "ROC-AUC",
            "F1",
        ],
        "radar": radar,
        "insights": insights,
    }
