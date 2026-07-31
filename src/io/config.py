"""설정 로드 및 외부 data_root 경로 해석."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 프로젝트 루트: .../LocalSubsidies_SupervisedLearning
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Run별로 격리하는 data_root 하위 키 (raw / raw_inference 는 공유)
RUN_SCOPED_PATH_KEYS = frozenset({"interim", "processed", "algorithms"})


def get_active_run_id(run_id: str | None = None) -> str | None:
    """명시 run_id 또는 환경변수 LSL_RUN_ID."""
    if run_id and str(run_id).strip():
        return str(run_id).strip()
    env = os.environ.get("LSL_RUN_ID")
    if env and env.strip():
        return env.strip()
    return None


def run_workspace(cfg: dict[str, Any], run_id: str | None = None) -> Path | None:
    """
    Run 산출물 루트: {data_root}/runs/{run_id}/
    run_id가 없으면 None (전역 경로 사용 — 튜닝 등 UI 밖 스크립트).
    """
    rid = get_active_run_id(run_id)
    if not rid:
        return None
    return get_data_root(cfg) / "runs" / rid


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


def load_tune_config(
    *,
    default_path: Path | None = None,
    tune_path: Path | None = None,
    tune_local_path: Path | None = None,
    local_path: Path | None = None,
) -> dict[str, Any]:
    """default.yaml + tune.yaml + tune_local.yaml(선택) + local.yaml — 12·tune_batch 전용.

    웹 API·run_config 는 읽지 않는다. data_root 만 local.yaml 과 공유.
    """
    cfg = load_config(default_path=default_path, local_path=local_path)
    tune_path = tune_path or PROJECT_ROOT / "configs" / "tune.yaml"
    if tune_path.exists():
        with open(tune_path, encoding="utf-8") as f:
            tune_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, tune_cfg)
    tune_local_path = tune_local_path or PROJECT_ROOT / "configs" / "tune_local.yaml"
    if tune_local_path.exists():
        with open(tune_local_path, encoding="utf-8") as f:
            tune_local = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, tune_local)
    return cfg


def resolve_tune_run_id(cfg: dict[str, Any], cli_run_id: str | None = None) -> str | None:
    """튜닝용 Run ID: CLI > LSL_RUN_ID > tune.yaml data_run_id."""
    if cli_run_id and str(cli_run_id).strip():
        return str(cli_run_id).strip()
    env = get_active_run_id()
    if env:
        return env
    data_rid = cfg.get("data_run_id")
    if data_rid and str(data_rid).strip():
        return str(data_rid).strip()
    return None


def apply_tune_run_id(cfg: dict[str, Any], cli_run_id: str | None = None) -> str | None:
    """resolve_tune_run_id 결과를 LSL_RUN_ID 에 반영."""
    rid = resolve_tune_run_id(cfg, cli_run_id)
    if rid:
        os.environ["LSL_RUN_ID"] = rid
    return rid


def resolve_tune_output_dir(cfg: dict[str, Any]) -> Path:
    """outputs/reports/tuning/{output_tag}/ — 튜닝 산출물 버전 폴더."""
    tag = str(cfg.get("output_tag") or "v1").strip() or "v1"
    base = resolve_repo_path(cfg, "reports_tuning")
    out = base / tag
    out.mkdir(parents=True, exist_ok=True)
    return out


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


def resolve_data_path(
    cfg: dict[str, Any],
    key: str,
    *,
    run_id: str | None = None,
) -> Path:
    """
    paths 섹션 키에 해당하는 경로.
    interim / processed / algorithms 는 LSL_RUN_ID(또는 run_id)가 있으면
    {data_root}/runs/{run_id}/{key}/ 아래로 격리한다.
    raw / raw_inference 는 항상 data_root 공유.
    """
    rel = cfg.get("paths", {}).get(key)
    if not rel:
        raise KeyError(f"configs.paths.{key} 가 없습니다.")
    if key in RUN_SCOPED_PATH_KEYS:
        ws = run_workspace(cfg, run_id)
        if ws is not None:
            return ws / rel
    return get_data_root(cfg) / rel


def resolve_repo_path(cfg: dict[str, Any], key: str) -> Path:
    """워크스페이스(프로젝트) 상대 경로."""
    rel = cfg.get("paths", {}).get(key)
    if not rel:
        raise KeyError(f"configs.paths.{key} 가 없습니다.")
    return PROJECT_ROOT / rel


def resolve_run_reports_dir(cfg: dict[str, Any], run_id: str | None = None) -> Path | None:
    """Run별 리포트(누수점검 JSON 등). run_id 없으면 None."""
    ws = run_workspace(cfg, run_id)
    if ws is None:
        return None
    return ws / "reports"


def resolve_algo_dir(
    cfg: dict[str, Any],
    algo: str,
    *,
    run_id: str | None = None,
) -> Path:
    """
    알고리즘별 산출물 루트.
    Run 격리: {data_root}/runs/{run_id}/algorithms/{algo}/
    """
    return resolve_data_path(cfg, "algorithms", run_id=run_id) / algo


def resolve_algo_scores_dir(
    cfg: dict[str, Any],
    algo: str,
    kind: str = "test",
    *,
    run_id: str | None = None,
) -> Path:
    """
    알고리즘별 행단위 점수 폴더 (로컬 전용).
    kind: test | inference
    """
    k = kind if kind in ("test", "inference") else "test"
    return resolve_algo_dir(cfg, algo, run_id=run_id) / "scores" / k


def resolve_algo_score_csv(
    cfg: dict[str, Any],
    algo: str,
    kind: str = "test",
    *,
    run_id: str | None = None,
) -> Path:
    """점수 CSV 경로 (신규 우선, 구 평면 경로 호환)."""
    k = kind if kind in ("test", "inference") else "test"
    primary = resolve_algo_scores_dir(cfg, algo, k, run_id=run_id) / f"{algo}_{k}_scores.csv"
    if primary.exists():
        return primary
    flat = resolve_algo_dir(cfg, algo, run_id=run_id) / "scores"
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
    *,
    run_id: str | None = None,
) -> Path:
    """상위1%/5% Excel 경로 (신규 우선)."""
    k = kind if kind in ("test", "inference") else "test"
    primary = (
        resolve_algo_scores_dir(cfg, algo, k, run_id=run_id) / f"{algo}_{k}_scores_top.xlsx"
    )
    if primary.exists():
        return primary
    legacy = resolve_algo_dir(cfg, algo, run_id=run_id) / "scores" / f"{algo}_{k}_scores_top.xlsx"
    if legacy.exists():
        return legacy
    return primary


def resolve_algo_report_dir(cfg: dict[str, Any], algo: str) -> Path:
    """워크스페이스 내 알고리즘별 집계 리포트 폴더 (공유·비격리)."""
    return resolve_repo_path(cfg, "reports") / algo


def ensure_algo_dirs(
    cfg: dict[str, Any],
    algorithms: list[str] | None = None,
    *,
    run_id: str | None = None,
) -> None:
    """
    알고리즘 폴더 골격 생성.
    Run 격리: LSL_RUN_ID/run_id 가 있을 때만 data_root/runs/{run_id}/algorithms 생성.
    run_id 없으면 전역 algorithms/interim/processed 는 만들지 않고 repo reports 만 생성.
    """
    algos = algorithms or cfg.get("algorithms", [])
    for algo in algos:
        resolve_algo_report_dir(cfg, algo).mkdir(parents=True, exist_ok=True)
    resolve_repo_path(cfg, "reports_comparison").mkdir(parents=True, exist_ok=True)

    rid = get_active_run_id(run_id)
    if not rid:
        return
    for algo in algos:
        d = resolve_algo_dir(cfg, algo, run_id=rid)
        (d / "scores" / "test").mkdir(parents=True, exist_ok=True)
        (d / "scores" / "inference").mkdir(parents=True, exist_ok=True)
    ops = resolve_data_path(cfg, "algorithms", run_id=rid) / "operations"
    ops.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
