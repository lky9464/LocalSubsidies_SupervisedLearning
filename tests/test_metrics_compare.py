"""eval_snapshot · compare frame 회귀 테스트."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.services.metrics import build_compare_frame, radar_chart_data, radar_chart_data
from src.evaluate.eval_snapshot import load_eval_maps_for_run, save_run_eval_summary


@pytest.fixture
def cfg(tmp_path: Path) -> dict:
    data_root = tmp_path / "data"
    algo_root = data_root / "algorithms"
    algo_root.mkdir(parents=True)
    return {
        "data_root": str(data_root),
        "paths": {"algorithms": "algorithms"},
    }


def _write_global_summary(cfg: dict, lift: dict, metrics: dict) -> None:
    root = Path(cfg["data_root"]) / "algorithms"
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "eval_summary.json", "w", encoding="utf-8") as f:
        json.dump({"lift": lift, "metrics": metrics}, f)


def _write_per_algo(cfg: dict, algo: str, lift: dict, metrics: dict) -> None:
    d = Path(cfg["data_root"]) / "algorithms" / algo
    d.mkdir(parents=True)
    with open(d / "eval_metrics.json", "w", encoding="utf-8") as f:
        json.dump({"lift": lift, "metrics": metrics}, f)


def test_load_prefers_run_snapshot_over_global(cfg: dict) -> None:
    _write_global_summary(
        cfg,
        lift={"catboost_v2": {"상위1%리프트(top_1pct_lift)": 99.0}},
        metrics={"catboost_v2": {"PR_AUC(AveragePrecision)": 0.99}},
    )
    save_run_eval_summary(
        cfg,
        "RUN001",
        {
            "lift": {
                "random_forest_v1": {
                    "상위1%리프트(top_1pct_lift)": 8.1,
                    "상위1%양성비율(top_1pct_positive_rate)": 0.42,
                    "상위1%양성포착비율(top_1pct_recall)": 0.11,
                    "상위5%리프트(top_5pct_lift)": 4.2,
                    "상위5%양성비율(top_5pct_positive_rate)": 0.25,
                    "상위5%양성포착비율(top_5pct_recall)": 0.35,
                }
            },
            "metrics": {"random_forest_v1": {"PR_AUC(AveragePrecision)": 0.91}},
        },
    )
    lift_map, _ = load_eval_maps_for_run(cfg, run_id="RUN001", algos=["random_forest_v1"])
    assert lift_map["random_forest_v1"]["상위1%리프트(top_1pct_lift)"] == 8.1
    # 전역 summary는 다른 algo(catboost_v2)도 병합 — compare frame은 ranking algo만 사용
    assert lift_map["catboost_v2"]["상위1%리프트(top_1pct_lift)"] == 99.0


def test_per_algo_fallback_when_missing_from_summaries(cfg: dict) -> None:
    _write_global_summary(
        cfg,
        lift={"catboost_v2": {"상위1%리프트(top_1pct_lift)": 9.0}},
        metrics={"catboost_v2": {"PR_AUC(AveragePrecision)": 0.95}},
    )
    _write_per_algo(
        cfg,
        "random_forest_v1",
        lift={
            "상위1%리프트(top_1pct_lift)": 7.5,
            "상위1%양성비율(top_1pct_positive_rate)": 0.38,
            "상위1%양성포착비율(top_1pct_recall)": 0.09,
            "상위5%리프트(top_5pct_lift)": 3.8,
            "상위5%양성비율(top_5pct_positive_rate)": 0.22,
            "상위5%양성포착비율(top_5pct_recall)": 0.31,
        },
        metrics={"PR_AUC(AveragePrecision)": 0.88},
    )
    ranking = [
        {
            "rank": 3,
            "algo": "random_forest_v1",
            "role": "candidate",
            "pr_auc": 0.88,
            "roc_auc": 0.8,
            "top1_lift": 7.5,
            "f1": 0.4,
        }
    ]
    df = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id="OLD_RUN")
    row = df.iloc[0]
    assert row["상위1%리프트"] == 7.5
    assert row["상위1%양성비중"] == pytest.approx(0.38)
    assert row["상위1%양성포착"] == pytest.approx(0.09)
    assert row["상위5%리프트"] == pytest.approx(3.8)
    assert row["상위5%양성비중"] == pytest.approx(0.22)
    assert row["상위5%양성포착"] == pytest.approx(0.31)


def test_db_ranking_fields_used_when_present(cfg: dict) -> None:
    ranking = [
        {
            "rank": 4,
            "algo": "catboost_v1",
            "role": "candidate",
            "pr_auc": 0.9,
            "top1_lift": 6.0,
            "top1_precision": 0.33,
            "top1_recall": 0.08,
            "top5_lift": 3.5,
            "top5_precision": 0.2,
            "top5_recall": 0.28,
            "f1": 0.35,
        }
    ]
    df = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id="RUNX")
    row = df.iloc[0]
    assert row["상위1%양성비중"] == pytest.approx(0.33)
    assert row["상위5%양성포착"] == pytest.approx(0.28)


def test_radar_includes_all_models_with_unique_ids(cfg: dict) -> None:
    ranking = [
        {"rank": 1, "algo": "catboost_v2", "role": "primary", "pr_auc": 0.95, "top1_lift": 9.0, "f1": 0.4},
        {"rank": 2, "algo": "random_forest_v2", "role": "aux", "pr_auc": 0.94, "top1_lift": 8.5, "f1": 0.38},
        {"rank": 3, "algo": "random_forest_v1", "role": "candidate", "pr_auc": 0.88, "top1_lift": 7.5, "f1": 0.35},
        {"rank": 4, "algo": "catboost_v1", "role": "candidate", "pr_auc": 0.87, "top1_lift": 7.0, "f1": 0.33},
    ]
    for algo in ("catboost_v2", "random_forest_v2", "random_forest_v1", "catboost_v1"):
        _write_per_algo(
            cfg,
            algo,
            lift={
                "상위1%리프트(top_1pct_lift)": 8.0,
                "상위1%양성비율(top_1pct_positive_rate)": 0.4,
                "상위1%양성포착비율(top_1pct_recall)": 0.1,
            },
            metrics={"PR_AUC(AveragePrecision)": 0.9},
        )

    df = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id="RUN4")
    radar = radar_chart_data(
        df,
        ["PR-AUC", "상위1%리프트", "상위1%양성비중", "상위1%양성포착"],
    )
    assert len(radar["series"]) == 4
    ids = {s["id"] for s in radar["series"]}
    assert ids == {"catboost_v2", "random_forest_v2", "random_forest_v1", "catboost_v1"}


def test_radar_keeps_model_with_partial_nulls(cfg: dict) -> None:
    ranking = [
        {"rank": 1, "algo": "catboost_v2", "role": "primary", "pr_auc": 0.95, "top1_lift": 9.0, "f1": 0.4},
        {"rank": 3, "algo": "random_forest_v1", "role": "candidate", "pr_auc": 0.88, "top1_lift": None, "f1": 0.35},
    ]
    _write_per_algo(
        cfg,
        "catboost_v2",
        lift={
            "상위1%리프트(top_1pct_lift)": 9.0,
            "상위1%양성비율(top_1pct_positive_rate)": 0.4,
            "상위1%양성포착비율(top_1pct_recall)": 0.1,
        },
        metrics={"PR_AUC(AveragePrecision)": 0.95},
    )
    df = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id="RUNP")
    radar = radar_chart_data(
        df,
        ["PR-AUC", "상위1%리프트", "상위1%양성비중", "상위1%양성포착"],
    )
    assert len(radar["series"]) == 2
    rf = next(s for s in radar["series"] if s["id"] == "random_forest_v1")
    assert rf["values"]["PR-AUC"] == 0.0  # 2모델 중 최솟값 → 정규화 0
    assert rf["values"]["상위1%리프트"] == 0.0


def test_legacy_gradient_boosting_id_resolves_v1_eval(cfg: dict) -> None:
    """DB legacy `gradient_boosting` → gradient_boosting_v1 폴더 eval 조회."""
    _write_per_algo(
        cfg,
        "gradient_boosting_v1",
        lift={
            "상위1%리프트(top_1pct_lift)": 6.2,
            "상위1%양성비율(top_1pct_positive_rate)": 0.31,
            "상위1%양성포착비율(top_1pct_recall)": 0.07,
        },
        metrics={"PR_AUC(AveragePrecision)": 0.86},
    )
    ranking = [
        {
            "rank": 5,
            "algo": "gradient_boosting",
            "role": "candidate",
            "pr_auc": 0.86,
            "top1_lift": 6.2,
            "f1": 0.3,
        }
    ]
    df = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id="RUNGB")
    row = df.iloc[0]
    assert row["algo_key"] == "gradient_boosting"
    assert row["알고리즘"] == "Gradient Boosting (v1)"
    assert row["상위1%리프트"] == pytest.approx(6.2)
    assert row["상위1%양성비중"] == pytest.approx(0.31)

    radar = radar_chart_data(
        df,
        ["PR-AUC", "상위1%리프트", "상위1%양성비중", "상위1%양성포착"],
    )
    assert len(radar["series"]) == 1
    assert radar["series"][0]["id"] == "gradient_boosting"
    assert radar["series"][0]["name"] == "Gradient Boosting (v1)"


def test_all_v1_families_in_radar(cfg: dict) -> None:
    families = [
        "catboost_v1",
        "stacked_ensemble_v1",
        "easy_ensemble_v1",
        "gradient_boosting_v1",
        "random_forest_v1",
    ]
    ranking = []
    for i, algo in enumerate(families, start=1):
        _write_per_algo(
            cfg,
            algo,
            lift={
                "상위1%리프트(top_1pct_lift)": 5.0 + i,
                "상위1%양성비율(top_1pct_positive_rate)": 0.3,
                "상위1%양성포착비율(top_1pct_recall)": 0.08,
            },
            metrics={"PR_AUC(AveragePrecision)": 0.8 + i * 0.01},
        )
        ranking.append(
            {
                "rank": i,
                "algo": algo,
                "role": "candidate",
                "pr_auc": 0.8 + i * 0.01,
                "top1_lift": 5.0 + i,
                "f1": 0.3,
            }
        )
    df = build_compare_frame(cfg, ranking, allow_global_fallback=False, run_id="RUNALL")
    radar = radar_chart_data(
        df,
        ["PR-AUC", "상위1%리프트", "상위1%양성비중", "상위1%양성포착"],
    )
    assert len(radar["series"]) == 5
    assert len({s["id"] for s in radar["series"]}) == 5
