"""Model comparison."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.constants import METRIC_HELP
from api.deps import get_cfg, get_repo
from api.serializers import df_to_records, matrix_to_payload
from api.services.metrics import build_compare_frame, radar_chart_data
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

    metric_list = [m.strip() for m in metrics.split(",")] if metrics else None
    radar = radar_chart_data(compare, metric_list)

    rank_meta: dict[str, str] = {}
    rank_path = resolve_data_path(cfg, "algorithms") / "operations" / "model_ranking.json"
    _, rank_meta = load_ranking_artifact(rank_path)

    labels_map = build_algo_labels_map(cfg)
    return {
        "run_id": run_id,
        "empty": ranking_empty,
        "ranking": df_to_records(compare),
        "ranking_confidence": rank_meta.get("ranking_confidence"),
        "ranking_note": rank_meta.get("ranking_note"),
        "primary": primary,
        "aux": aux,
        "primary_label": resolve_algo_label(primary, labels_map) if primary else primary,
        "aux_label": resolve_algo_label(aux, labels_map) if aux else aux,
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
        "test_matrices": test_block,
    }
