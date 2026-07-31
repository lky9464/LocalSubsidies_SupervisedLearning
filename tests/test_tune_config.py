"""튜닝 설정·산출 경로."""

from __future__ import annotations

from pathlib import Path

from src.io.config import (
    apply_tune_run_id,
    load_config,
    load_tune_config,
    resolve_tune_output_dir,
    resolve_tune_run_id,
)


def test_load_tune_config_has_tune_block() -> None:
    cfg = load_tune_config()
    assert cfg.get("output_tag") == "v3"
    assert cfg.get("data_run_id") == "run_20260730_172901"
    tune = cfg.get("tune") or {}
    assert tune.get("split_mode") == "nested_group_random"
    assert "random_forest_v1" in (tune.get("algorithms") or [])
    assert (cfg.get("model_params") or {}).get("catboost_v3")


def test_load_tune_config_default_yaml_has_no_tune_block() -> None:
    cfg = load_config()
    assert "tune" not in cfg


def test_resolve_tune_run_id_priority() -> None:
    cfg = load_tune_config()
    assert resolve_tune_run_id(cfg, "cli_run") == "cli_run"
    assert resolve_tune_run_id(cfg, None) == "run_20260730_172901"


def test_apply_tune_run_id_sets_env(monkeypatch) -> None:
    monkeypatch.delenv("LSL_RUN_ID", raising=False)
    cfg = load_tune_config()
    rid = apply_tune_run_id(cfg, "env_test_run")
    assert rid == "env_test_run"
    import os

    assert os.environ.get("LSL_RUN_ID") == "env_test_run"


def test_resolve_tune_output_dir() -> None:
    cfg = load_tune_config()
    out = resolve_tune_output_dir(cfg)
    assert out.name == "v3"
    assert out.parent.name == "tuning"
    assert out.is_dir()


def test_tune_output_dir_matches_repo_layout() -> None:
    cfg = load_tune_config()
    out = resolve_tune_output_dir(cfg)
    repo = Path(__file__).resolve().parents[1]
    assert out == repo / "outputs" / "reports" / "tuning" / "v3"
