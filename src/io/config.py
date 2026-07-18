"""설정 로드 및 외부 data_root 경로 해석."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 프로젝트 루트: .../LocalSubsidies_SupervisedLearning
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_config(
    default_path: Path | None = None,
    local_path: Path | None = None,
) -> dict[str, Any]:
    """default.yaml + local.yaml(선택)을 병합한다."""
    default_path = default_path or PROJECT_ROOT / "configs" / "default.yaml"
    local_path = local_path or PROJECT_ROOT / "configs" / "local.yaml"

    with open(default_path, encoding="utf-8") as f:
        cfg: dict[str, Any] = yaml.safe_load(f) or {}

    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            local_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, local_cfg)

    # 환경변수가 있으면 data_root 우선
    env_root = os.environ.get("LSL_DATA_ROOT")
    if env_root:
        cfg["data_root"] = env_root

    return cfg


def get_data_root(cfg: dict[str, Any]) -> Path:
    """프로젝트 밖 데이터 루트를 반환한다. 미설정 시 명확히 오류."""
    root = cfg.get("data_root")
    if not root:
        raise ValueError(
            "data_root가 설정되지 않았습니다. "
            "configs/local.yaml.example을 복사해 configs/local.yaml을 만들거나 "
            "환경변수 LSL_DATA_ROOT를 설정하세요."
        )
    path = Path(root).expanduser().resolve()
    return path


def resolve_data_path(cfg: dict[str, Any], key: str) -> Path:
    """paths 섹션 키에 해당하는 data_root 하위 경로."""
    rel = cfg.get("paths", {}).get(key)
    if not rel:
        raise KeyError(f"configs.paths.{key} 가 없습니다.")
    return get_data_root(cfg) / rel


def resolve_repo_path(cfg: dict[str, Any], key: str) -> Path:
    """워크스페이스(프로젝트) 상대 경로."""
    rel = cfg.get("paths", {}).get(key)
    if not rel:
        raise KeyError(f"configs.paths.{key} 가 없습니다.")
    return PROJECT_ROOT / rel


def resolve_algo_dir(cfg: dict[str, Any], algo: str) -> Path:
    """
    알고리즘별 산출물 루트.
    예: {data_root}/algorithms/catboost/
    """
    return resolve_data_path(cfg, "algorithms") / algo


def resolve_algo_scores_dir(
    cfg: dict[str, Any],
    algo: str,
    kind: str = "test",
) -> Path:
    """
    알고리즘별 행단위 점수 폴더 (로컬 전용).
    kind: test | inference
    → {data_root}/algorithms/{algo}/scores/{kind}/
    """
    k = kind if kind in ("test", "inference") else "test"
    return resolve_algo_dir(cfg, algo) / "scores" / k


def resolve_algo_score_csv(
    cfg: dict[str, Any],
    algo: str,
    kind: str = "test",
) -> Path:
    """
    점수 CSV 경로 (신규 우선, 구 평면 경로 호환).
    신규: scores/{kind}/{algo}_{kind}_scores.csv
    구:   scores/{algo}_{kind}_scores.csv 또는 scores/inference_scores.csv
    """
    k = kind if kind in ("test", "inference") else "test"
    primary = resolve_algo_scores_dir(cfg, algo, k) / f"{algo}_{k}_scores.csv"
    if primary.exists():
        return primary
    flat = resolve_algo_dir(cfg, algo) / "scores"
    legacy = flat / f"{algo}_{k}_scores.csv"
    if legacy.exists():
        return legacy
    if k == "inference":
        old_inf = flat / "inference_scores.csv"
        if old_inf.exists():
            return old_inf
    return primary


def resolve_algo_score_top_xlsx(
    cfg: dict[str, Any],
    algo: str,
    kind: str = "test",
) -> Path:
    """상위1%/5% Excel 경로 (신규 우선)."""
    k = kind if kind in ("test", "inference") else "test"
    primary = resolve_algo_scores_dir(cfg, algo, k) / f"{algo}_{k}_scores_top.xlsx"
    if primary.exists():
        return primary
    legacy = resolve_algo_dir(cfg, algo) / "scores" / f"{algo}_{k}_scores_top.xlsx"
    if legacy.exists():
        return legacy
    return primary


def resolve_algo_report_dir(cfg: dict[str, Any], algo: str) -> Path:
    """워크스페이스 내 알고리즘별 집계 리포트 폴더."""
    return resolve_repo_path(cfg, "reports") / algo


def ensure_algo_dirs(cfg: dict[str, Any], algorithms: list[str] | None = None) -> None:
    """알고리즘 5종 폴더 골격 생성 (공통 raw/interim/processed는 별도)."""
    algos = algorithms or cfg.get("algorithms", [])
    for algo in algos:
        d = resolve_algo_dir(cfg, algo)
        (d / "scores" / "test").mkdir(parents=True, exist_ok=True)
        (d / "scores" / "inference").mkdir(parents=True, exist_ok=True)
        resolve_algo_report_dir(cfg, algo).mkdir(parents=True, exist_ok=True)
    resolve_repo_path(cfg, "reports_comparison").mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
