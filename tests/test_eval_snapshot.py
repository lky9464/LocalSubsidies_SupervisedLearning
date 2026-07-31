"""eval_snapshot 전역 fallback 회귀 테스트."""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluate.eval_snapshot import load_eval_maps_for_run, save_run_eval_summary


def _cfg(tmp_path: Path) -> dict:
    data_root = tmp_path / "data"
    (data_root / "algorithms").mkdir(parents=True)
    return {"data_root": str(data_root), "paths": {"algorithms": "algorithms"}}


def _write_global_summary(cfg: dict, lift: dict, metrics: dict) -> None:
    root = Path(cfg["data_root"]) / "algorithms"
    with open(root / "eval_summary.json", "w", encoding="utf-8") as f:
        json.dump({"lift": lift, "metrics": metrics}, f)


def _write_per_algo(cfg: dict, algo: str, lift: dict, metrics: dict) -> None:
    d = Path(cfg["data_root"]) / "algorithms" / algo
    d.mkdir(parents=True)
    with open(d / "eval_metrics.json", "w", encoding="utf-8") as f:
        json.dump({"lift": lift, "metrics": metrics}, f)


def test_global_summary_merged_when_run_scoped_missing(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_global_summary(
        cfg,
        lift={"catboost_v2": {"상위1%리프트(top_1pct_lift)": 99.0}},
        metrics={"catboost_v2": {"PR_AUC(AveragePrecision)": 0.99}},
    )
    save_run_eval_summary(
        cfg,
        "RUN001",
        {
            "lift": {"random_forest_v1": {"상위1%리프트(top_1pct_lift)": 8.1}},
            "metrics": {"random_forest_v1": {"PR_AUC(AveragePrecision)": 0.91}},
        },
    )
    lift_map, _ = load_eval_maps_for_run(
        cfg, run_id="RUN001", algos=["random_forest_v1"]
    )
    assert lift_map["random_forest_v1"]["상위1%리프트(top_1pct_lift)"] == 8.1
    assert lift_map["catboost_v2"]["상위1%리프트(top_1pct_lift)"] == 99.0


def test_global_per_algo_fallback_when_run_folder_empty(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_per_algo(
        cfg,
        "random_forest_v1",
        lift={
            "상위1%리프트(top_1pct_lift)": 7.5,
            "상위1%양성비율(top_1pct_positive_rate)": 0.38,
        },
        metrics={"PR_AUC(AveragePrecision)": 0.88},
    )
    lift_map, metrics_map = load_eval_maps_for_run(
        cfg, run_id="OLD_RUN", algos=["random_forest_v1"]
    )
    assert lift_map["random_forest_v1"]["상위1%양성비율(top_1pct_positive_rate)"] == 0.38
    assert metrics_map["random_forest_v1"]["PR_AUC(AveragePrecision)"] == 0.88


def test_run_scoped_per_algo_takes_priority_over_global(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    _write_per_algo(
        cfg,
        "catboost_v1",
        lift={"상위1%리프트(top_1pct_lift)": 5.0},
        metrics={"PR_AUC(AveragePrecision)": 0.80},
    )
    run_dir = Path(cfg["data_root"]) / "runs" / "RUNX" / "algorithms" / "catboost_v1"
    run_dir.mkdir(parents=True)
    with open(run_dir / "eval_metrics.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "lift": {"상위1%리프트(top_1pct_lift)": 9.0},
                "metrics": {"PR_AUC(AveragePrecision)": 0.95},
            },
            f,
        )
    lift_map, metrics_map = load_eval_maps_for_run(
        cfg, run_id="RUNX", algos=["catboost_v1"]
    )
    assert lift_map["catboost_v1"]["상위1%리프트(top_1pct_lift)"] == 9.0
    assert metrics_map["catboost_v1"]["PR_AUC(AveragePrecision)"] == 0.95
