from pathlib import Path

import pytest

from src.models.tune import _validate_preprocess_for_tune


def test_validate_preprocess_split_mode_ok() -> None:
    cfg = {"require_preprocess_split_mode": "group_random"}
    bundle = {"split": {"mode": "group_random"}}
    _validate_preprocess_for_tune(cfg, Path("."), bundle)


def test_validate_preprocess_split_mode_fail() -> None:
    cfg = {"require_preprocess_split_mode": "group_random"}
    bundle = {"split": {"mode": "random"}}
    with pytest.raises(RuntimeError, match="split.mode"):
        _validate_preprocess_for_tune(cfg, Path("."), bundle)
