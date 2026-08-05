"""model_insights · PR curve 단위 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

from api.services.model_insights import (
    build_role_insight_panels,
    load_shap_top10,
    resolve_shap_total_path,
)
from api.services.metrics import radar_chart_data
from src.evaluate.metrics import compute_pr_curve_points
from src.evaluate.shap_importance import write_shap_total_xlsx
from src.io.config import resolve_run_algo_report_dir


@pytest.fixture
def cfg(tmp_path: Path) -> dict:
    data_root = tmp_path / "data"
    reports = tmp_path / "repo" / "outputs" / "reports"
    reports.mkdir(parents=True)
    return {
        "data_root": str(data_root),
        "paths": {
            "algorithms": "algorithms",
            "reports": str(reports.relative_to(tmp_path / "repo")),
        },
        "feature_importance": {"top_n": 10},
    }


def test_compute_pr_curve_points() -> None:
    X, y = make_classification(
        n_samples=200,
        n_features=6,
        weights=[0.9, 0.1],
        random_state=42,
    )
    model = RandomForestClassifier(n_estimators=10, random_state=42)
    model.fit(X, y)
    proba = model.predict_proba(X)[:, 1]
    curve = compute_pr_curve_points(y, proba, max_points=20)
    assert curve is not None
    assert len(curve["recall"]) <= 20
    assert curve["pr_auc"] > 0
    assert 0 < curve["baseline"] < 1


def test_load_shap_top10_run_scoped(cfg: dict, tmp_path: Path) -> None:
    run_id = "RUN001"
    algo = "random_forest_v1"
    run_dir = resolve_run_algo_report_dir(cfg, algo, run_id=run_id)
    assert run_dir is not None
    run_dir.mkdir(parents=True)

    df = pd.DataFrame(
        [
            {
                "순위(rank)": 1,
                "알고리즘(algorithm)": algo,
                "피처명(feature)": "F_A",
                "피처명한글(feature_ko)": "A",
                "기여도비중(importance_share)": 0.5,
                "기여방향(direction)": "+",
                "기여방향표시(direction_label)": "양(+)",
            },
            {
                "순위(rank)": 2,
                "알고리즘(algorithm)": algo,
                "피처명(feature)": "F_B",
                "피처명한글(feature_ko)": "B",
                "기여도비중(importance_share)": 0.3,
                "기여방향(direction)": "-",
                "기여방향표시(direction_label)": "음(-)",
            },
        ]
    )
    write_shap_total_xlsx(run_dir / "SHAP_total.xlsx", df)

    path = resolve_shap_total_path(cfg, algo, run_id=run_id)
    assert path is not None and path.exists()
    top = load_shap_top10(cfg, algo, run_id=run_id, top_n=10)
    assert len(top) == 2
    assert top[0]["feature"] == "F_A"
    assert top[1]["signed_share"] < 0


def test_radar_includes_axis_scales_and_roles(cfg: dict) -> None:
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "알고리즘": "RF",
                "algo_key": "random_forest_v1",
                "역할": "primary",
                "PR-AUC": 0.7,
                "상위1%리프트": 10.0,
                "상위1%양성비중": 0.4,
                "상위1%양성포착": 0.1,
            },
            {
                "알고리즘": "CB",
                "algo_key": "catboost_v1",
                "역할": "aux",
                "PR-AUC": 0.8,
                "상위1%리프트": 12.0,
                "상위1%양성비중": 0.5,
                "상위1%양성포착": 0.12,
            },
        ]
    )
    radar = radar_chart_data(df, ["PR-AUC", "상위1%리프트", "상위1%양성비중"])
    assert radar["axis_scales"]["PR-AUC"]["max"] == 0.8
    assert radar["series"][0]["default_visible"] is True
    assert radar["series"][0]["raw"]["PR-AUC"] == 0.7


def test_build_role_insight_panels_reference_missing(cfg: dict, tmp_path: Path) -> None:
    algo_root = Path(cfg["data_root"]) / "algorithms" / "random_forest_v1"
    algo_root.mkdir(parents=True)
    curve = {"recall": [0, 1], "precision": [1, 0.5], "pr_auc": 0.6, "baseline": 0.01}
    with open(algo_root / "eval_metrics.json", "w", encoding="utf-8") as f:
        json.dump({"metrics": {}, "lift": {}, "pr_curve": curve}, f)

    ranking = [
        {"algo": "random_forest_v1", "role": "primary", "rank": 1},
        {"algo": "catboost_v1", "role": "aux", "rank": 2},
    ]
    panels = build_role_insight_panels(
        cfg,
        ranking,
        run_id=None,
        labels_map={"random_forest_v1": "RF", "catboost_v1": "CB"},
    )
    assert panels["pr_curve"]["primary"]["available"] is True
    assert panels["pr_curve"]["reference"]["available"] is False
    assert "2개 모델" in panels["pr_curve"]["reference"]["reason"]
