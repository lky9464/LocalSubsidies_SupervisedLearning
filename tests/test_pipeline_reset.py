"""Run-scoped paths and pipeline reset helpers."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

from src.io.config import resolve_algo_dir, resolve_data_path, run_workspace
from src.pipeline.reset import earliest_step_id, steps_from


def test_resolve_data_path_run_scoped(tmp_path: Path, monkeypatch) -> None:
    cfg = {
        "data_root": str(tmp_path),
        "paths": {
            "raw": "raw",
            "interim": "interim",
            "processed": "processed",
            "algorithms": "algorithms",
        },
    }
    monkeypatch.delenv("LSL_RUN_ID", raising=False)
    assert resolve_data_path(cfg, "raw") == tmp_path / "raw"
    assert resolve_data_path(cfg, "interim") == tmp_path / "interim"

    monkeypatch.setenv("LSL_RUN_ID", "run_test_1")
    assert resolve_data_path(cfg, "raw") == tmp_path / "raw"
    assert resolve_data_path(cfg, "interim") == tmp_path / "runs" / "run_test_1" / "interim"
    assert resolve_algo_dir(cfg, "catboost_v2") == (
        tmp_path / "runs" / "run_test_1" / "algorithms" / "catboost_v2"
    )
    assert run_workspace(cfg) == tmp_path / "runs" / "run_test_1"


def test_steps_from_and_earliest() -> None:
    assert steps_from("merge")[0] == "merge"
    assert steps_from("merge")[-1] == "ops_queue"
    assert steps_from("evaluate") == [
        "evaluate",
        "ranking",
        "report",
        "ops_queue",
    ]
    assert earliest_step_id(["ops_queue", "train", "evaluate"]) == "train"


def test_inference_score_path_run_scoped(tmp_path: Path, monkeypatch) -> None:
    from src.scoring.inference_helpers import inference_score_path

    cfg = {
        "data_root": str(tmp_path),
        "paths": {"algorithms": "algorithms"},
    }
    monkeypatch.delenv("LSL_RUN_ID", raising=False)
    # API without run_id → global (legacy); with run_id → runs/{id}/...
    global_p = inference_score_path(cfg, "catboost_v2")
    assert "runs" not in str(global_p).replace("\\", "/")
    run_p = inference_score_path(cfg, "catboost_v2", run_id="run_abc")
    assert run_p == (
        tmp_path
        / "runs"
        / "run_abc"
        / "algorithms"
        / "catboost_v2"
        / "scores"
        / "inference"
        / "catboost_v2_inference_scores.csv"
    )


def test_reset_clears_steps_and_dirs(tmp_path: Path, monkeypatch) -> None:
    from src.pipeline.reset import reset_pipeline_from

    cfg = {
        "data_root": str(tmp_path),
        "paths": {
            "interim": "interim",
            "processed": "processed",
            "algorithms": "algorithms",
        },
    }
    run_id = "run_reset_1"
    monkeypatch.setenv("LSL_RUN_ID", run_id)
    ws = tmp_path / "runs" / run_id
    (ws / "interim").mkdir(parents=True)
    (ws / "interim" / "merged.csv").write_text("a", encoding="utf-8")
    (ws / "algorithms" / "catboost_v2").mkdir(parents=True)
    (ws / "algorithms" / "catboost_v2" / "model.joblib").write_bytes(b"x")

    repo = MagicMock()
    repo.delete_steps = MagicMock(return_value=2)
    repo.clear_ranking = MagicMock()
    repo.clear_ops_queue = MagicMock()

    out = reset_pipeline_from(cfg, repo, run_id, "merge")
    assert out["from_step"] == "merge"
    assert "train" in out["cleared_steps"]
    repo.delete_steps.assert_called_once()
    repo.clear_ranking.assert_called_once_with(run_id)
    repo.clear_ops_queue.assert_called_once_with(run_id)
    assert not (ws / "interim" / "merged.csv").exists()
    assert not (ws / "algorithms" / "catboost_v2" / "model.joblib").exists()
