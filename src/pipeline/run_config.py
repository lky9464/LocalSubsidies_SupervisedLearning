"""run별 설정 로드/저장."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from src.io.config import get_data_root


def run_config_path(cfg: dict[str, Any], run_id: str) -> Path:
    return get_data_root(cfg) / "runs" / run_id / "run_config.yaml"


def default_run_config(cfg: dict[str, Any]) -> dict[str, Any]:
    split = dict(cfg.get("split", {}))
    return {
        "split": {
            "mode": "time",
            "train_start": split.get("train_start", "202401"),
            "train_end": split.get("train_end", "202506"),
            "test_start": split.get("test_start", "202507"),
            "test_end": split.get("test_end", "202512"),
            "test_size": 0.3,
            "random_state": int(cfg.get("random_seed", 42)),
        },
        "algorithms": list(cfg.get("algorithms", [])),
        "exclude_features_extra": [],
    }


def load_run_config(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    path = run_config_path(cfg, run_id)
    base = default_run_config(cfg)
    if not path.exists():
        return base
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    # shallow merge
    for k, v in loaded.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    return base


def save_run_config(cfg: dict[str, Any], run_id: str, run_cfg: dict[str, Any]) -> Path:
    path = run_config_path(cfg, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(run_cfg, f, allow_unicode=True, sort_keys=False)
    return path


def warn_test_share(train_start: str, train_end: str, test_start: str, test_end: str) -> str | None:
    """기간 모드 Test 비중 대략 경고 (YYYYMM 정수 차이 근사)."""
    try:
        def months(a: str, b: str) -> int:
            ay, am = int(a[:4]), int(a[4:6])
            by, bm = int(b[:4]), int(b[4:6])
            return (by - ay) * 12 + (bm - am) + 1

        tr = months(train_start, train_end)
        te = months(test_start, test_end)
        total = tr + te
        if total <= 0:
            return "Train/Test 기간이 올바르지 않습니다."
        share = te / total
        if share < 0.15 or share > 0.40:
            return (
                f"Test 기간 비중이 약 {share:.0%} 입니다. "
                "통상 15%~40%를 벗어나 설정이 부적절할 수 있습니다."
            )
    except Exception:  # noqa: BLE001
        return None
    return None
