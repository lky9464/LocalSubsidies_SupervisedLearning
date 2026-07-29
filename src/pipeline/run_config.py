"""run별 설정 로드/저장."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.io.config import get_data_root


def pipeline_run_id() -> str:
    """Job/파이프라인 worker 가 설정하는 현재 Run ID (없으면 빈 문자열)."""
    return (os.environ.get("LSL_RUN_ID") or "").strip()


def resolve_pipeline_algorithms(cfg: dict[str, Any]) -> list[str]:
    """LSL_RUN_ID 가 있으면 run_config.algorithms, 없으면 default.yaml algorithms."""
    run_id = pipeline_run_id()
    if run_id:
        algos = load_run_config(cfg, run_id).get("algorithms")
        if algos:
            return list(algos)
    return list(cfg.get("algorithms") or [])


def resolve_pipeline_run_id(cfg: dict[str, Any], *, repo: Any | None = None) -> str:
    """LSL_RUN_ID → ops DB 최신 run → 새 run_id 순."""
    run_id = pipeline_run_id()
    if run_id:
        return run_id
    if repo is not None:
        latest = repo.get_latest_run_id()
        if latest:
            return latest
    from src.pipeline.runner import new_run_id

    return new_run_id()


def run_config_path(cfg: dict[str, Any], run_id: str) -> Path:
    return get_data_root(cfg) / "runs" / run_id / "run_config.yaml"


def default_run_config(cfg: dict[str, Any]) -> dict[str, Any]:
    from src.models.registry import default_train_algo_ids

    split = dict(cfg.get("split", {}))
    return {
        "split": {
            "mode": str(split.get("mode", "random")),
            "group_key": str(split.get("group_key", "PFM_BIZ_ID+INST_ID")),
            "train_start": split.get("train_start", "202401"),
            "train_end": split.get("train_end", "202512"),
            "test_start": split.get("test_start", "202507"),
            "test_end": split.get("test_end", "202512"),
            "test_size": float(split.get("test_size", 0.3)),
            "random_state": int(split.get("random_state", cfg.get("random_seed", 42))),
            "valid_start": split.get("valid_start", "202504"),
            "valid_end": split.get("valid_end", "202506"),
        },
        "algorithms": default_train_algo_ids(cfg),
        "exclude_features_extra": [],
        # algo_id → {param: value} ; default.yaml model_params 위에 덮어씀
        "model_params": {},
        # 데이터 등록에서 선택한 CSV (Job 시작 시 동결). data_root 상대경로.
        "raw_files": [],
        "raw_inference_files": [],
        # 추론 실행 시 --algo 로 선택한 algo_id (순서: 1=주, 2=보)
        "inference_algorithms": [],
        "split_committed": False,
        "algorithms_committed": False,
    }


def resolve_run_raw_paths(
    cfg: dict[str, Any], run_cfg: dict[str, Any], *, kind: str = "train"
) -> list[Path]:
    """run_config의 raw_files / raw_inference_files → 절대 Path 목록."""
    key = "raw_inference_files" if kind == "inference" else "raw_files"
    rels = [str(x).replace("\\", "/") for x in (run_cfg.get(key) or []) if str(x).strip()]
    root = get_data_root(cfg)
    return [root / r for r in rels]


def freeze_raw_selection(
    cfg: dict[str, Any],
    run_id: str,
    selected_rel_paths: list[str],
    *,
    kind: str = "train",
) -> dict[str, Any]:
    """현재 선택 CSV를 run_config에 동결 저장."""
    key = "raw_inference_files" if kind == "inference" else "raw_files"
    rels = [str(x).replace("\\", "/") for x in selected_rel_paths if str(x).strip()]
    if not rels:
        label = "추론" if kind == "inference" else "학습·평가"
        raise ValueError(
            f"선택된 {label} CSV가 없습니다. 데이터 등록에서 사용할 파일을 체크한 뒤 "
            "「선택 저장」을 눌러 주세요."
        )
    run_cfg = load_run_config(cfg, run_id)
    run_cfg[key] = rels
    save_run_config(cfg, run_id, run_cfg)
    return run_cfg


def load_run_config(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    path = run_config_path(cfg, run_id)
    base = default_run_config(cfg)
    if not path.exists():
        return base
    with open(path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}
    # shallow merge (model_params 는 알고리즘별 1단 더 merge)
    for k, v in loaded.items():
        if k == "model_params" and isinstance(v, dict):
            merged_mp = dict(base.get("model_params") or {})
            for algo, params in v.items():
                if isinstance(params, dict):
                    merged_mp[algo] = {**(merged_mp.get(algo) or {}), **params}
                else:
                    merged_mp[algo] = params
            base["model_params"] = merged_mp
        elif isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k] = {**base[k], **v}
        else:
            base[k] = v
    # 구 options_committed → split·algorithms 둘 다 committed
    if base.get("options_committed") and "split_committed" not in loaded:
        base["split_committed"] = True
        base["algorithms_committed"] = True
    return base


def save_inference_algorithms(
    cfg: dict[str, Any],
    run_id: str,
    algo_ids: list[str],
) -> dict[str, Any]:
    """추론 Job 시작 시 선택 알고리즘을 run_config에 기록 (주·보 표시용)."""
    from src.models.registry import normalize_algo_id

    algos = [normalize_algo_id(a) for a in algo_ids if str(a).strip()]
    if not algos:
        raise ValueError("추론 알고리즘을 1개 이상 지정하세요.")
    run_cfg = load_run_config(cfg, run_id)
    run_cfg["inference_algorithms"] = algos
    save_run_config(cfg, run_id, run_cfg)
    return run_cfg


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
