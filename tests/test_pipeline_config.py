"""Pipeline config lock rules (split vs algorithms)."""

from __future__ import annotations

from unittest.mock import patch

from api.schemas.common import RunConfigUpdate
from api.services.pipeline import (
    algorithms_config_editable,
    config_update_allowed,
    settings_locked,
    split_config_locked,
)


def _prep_succeeded() -> dict[str, str]:
    return {
        "merge": "succeeded",
        "label": "succeeded",
        "preprocess": "succeeded",
        "leakage": "succeeded",
    }


def test_settings_locked_after_prep_without_train() -> None:
    step_map = _prep_succeeded()
    cfg: dict = {}
    with patch("api.services.pipeline.get_pipeline_abandon", return_value=False):
        with patch("api.services.pipeline.job_is_running", return_value=False):
            assert settings_locked(cfg, "run1", step_map) is True


def test_algorithms_editable_after_prep_before_train() -> None:
    step_map = _prep_succeeded()
    cfg: dict = {}
    with patch("api.services.pipeline.get_pipeline_abandon", return_value=False):
        with patch("api.services.pipeline.job_is_running", return_value=False):
            assert algorithms_config_editable(cfg, "run1", step_map) is True


def test_split_locked_after_merge() -> None:
    assert split_config_locked({"merge": "succeeded"}) is True


def test_algo_commit_allowed_after_prep_complete() -> None:
    step_map = _prep_succeeded()
    cfg: dict = {}
    body = RunConfigUpdate(
        algorithms=["random_forest_v2", "catboost_v2"],
        algorithms_committed=True,
    )
    with patch("api.services.pipeline.get_pipeline_abandon", return_value=False):
        with patch("api.services.pipeline.job_is_running", return_value=False):
            ok, reason = config_update_allowed(body, cfg, "run1", step_map)
    assert ok is True
    assert reason == ""


def test_split_change_blocked_after_merge() -> None:
    step_map = {"merge": "succeeded"}
    cfg: dict = {}
    body = RunConfigUpdate(split={"mode": "random"})
    with patch("api.services.pipeline.get_pipeline_abandon", return_value=False):
        with patch("api.services.pipeline.job_is_running", return_value=False):
            ok, reason = config_update_allowed(body, cfg, "run1", step_map)
    assert ok is False
    assert "분할" in reason


def test_algo_change_blocked_after_train_started() -> None:
    step_map = {**_prep_succeeded(), "train": "running"}
    cfg: dict = {}
    body = RunConfigUpdate(algorithms=["random_forest_v2", "catboost_v2"])
    with patch("api.services.pipeline.get_pipeline_abandon", return_value=False):
        with patch("api.services.pipeline.job_is_running", return_value=False):
            ok, reason = config_update_allowed(body, cfg, "run1", step_map)
    assert ok is False
    assert "05~10" in reason
