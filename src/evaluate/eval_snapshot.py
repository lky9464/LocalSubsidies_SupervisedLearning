"""Run별 07 평가 스냅샷 (모델 비교·과거 Run 조회용)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from src.io.config import get_data_root, resolve_algo_dir, resolve_data_path
from src.models.registry import algo_lookup_ids


def run_eval_summary_path(cfg: dict[str, Any], run_id: str) -> Path:
    return get_data_root(cfg) / "runs" / run_id / "eval_summary.json"


def save_run_eval_summary(cfg: dict[str, Any], run_id: str, summary: dict[str, Any]) -> Path:
    path = run_eval_summary_path(cfg, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    return path


def copy_run_eval_summary_from_global(cfg: dict[str, Any], run_id: str) -> Path | None:
    src = resolve_data_path(cfg, "algorithms", run_id=run_id) / "eval_summary.json"
    if not src.exists():
        return None
    dst = run_eval_summary_path(cfg, run_id)
    if src.resolve() == dst.resolve():
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def read_eval_summary_file(path: Path) -> tuple[dict, dict]:
    try:
        with open(path, encoding="utf-8") as f:
            summary = json.load(f)
    except OSError:
        return {}, {}
    return summary.get("lift") or {}, summary.get("metrics") or {}


def register_eval_entry(
    lift_map: dict[str, dict],
    metrics_map: dict[str, dict],
    algo_key: str,
    *,
    lift: dict | None = None,
    metrics: dict | None = None,
) -> None:
    """summary/per-algo 항목을 algo_id alias 전체에 등록."""
    lf = lift or {}
    m = metrics or {}
    if not lf and not m:
        return
    for alias in algo_lookup_ids(algo_key):
        if lf and alias not in lift_map:
            lift_map[alias] = lf
        if m and alias not in metrics_map:
            metrics_map[alias] = m


def _read_eval_metrics_file(path: Path) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def load_per_algo_eval_payload(
    cfg: dict[str, Any],
    algo: str,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run 격리 경로 우선 eval_metrics.json 전체 payload."""
    lookup_runs: list[str | None] = []
    if run_id:
        lookup_runs.append(run_id)
    lookup_runs.append(None)

    seen: set[Path] = set()
    for key in algo_lookup_ids(algo):
        for rid in lookup_runs:
            path = resolve_algo_dir(cfg, key, run_id=rid) / "eval_metrics.json"
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            if not path.exists():
                continue
            payload = _read_eval_metrics_file(path)
            if payload:
                return payload
    return {}


def load_per_algo_eval(
    cfg: dict[str, Any],
    algo: str,
    *,
    run_id: str | None = None,
) -> tuple[dict, dict]:
    """Run 격리 경로 우선, 없으면 전역 algorithms/{algo}/eval_metrics.json."""
    payload = load_per_algo_eval_payload(cfg, algo, run_id=run_id)
    return payload.get("metrics") or {}, payload.get("lift") or {}


def load_per_algo_pr_curve(
    cfg: dict[str, Any],
    algo: str,
    *,
    run_id: str | None = None,
) -> dict[str, Any] | None:
    """eval_metrics.json 의 pr_curve (Run 우선)."""
    payload = load_per_algo_eval_payload(cfg, algo, run_id=run_id)
    curve = payload.get("pr_curve")
    return curve if isinstance(curve, dict) else None


def pick_eval_for_algo(
    lift_map: dict[str, dict],
    metrics_map: dict[str, dict],
    algo: str,
) -> tuple[dict, dict]:
    for key in algo_lookup_ids(algo):
        lf = lift_map.get(key) or {}
        m = metrics_map.get(key) or {}
        if lf or m:
            return m, lf
    return {}, {}


def merge_eval_maps(
    lift_map: dict[str, dict],
    metrics_map: dict[str, dict],
    lift: dict,
    metrics: dict,
) -> None:
    for algo, lf in (lift or {}).items():
        register_eval_entry(lift_map, metrics_map, str(algo), lift=lf or {})
    for algo, m in (metrics or {}).items():
        register_eval_entry(lift_map, metrics_map, str(algo), metrics=m or {})


def load_eval_maps_for_run(
    cfg: dict[str, Any],
    *,
    run_id: str | None = None,
    algos: list[str] | None = None,
) -> tuple[dict, dict]:
    """
    lift/metrics 맵 (우선순위).
    1) runs/{run_id}/eval_summary.json
    2) runs/{run_id}/algorithms/eval_summary.json (Run 격리 시)
    3) {data_root}/algorithms/eval_summary.json (전역 · Run에 없는 algo 보충)
    4) algorithms/{algo}/eval_metrics.json (Run 우선 → 전역 fallback)
    """
    lift_map: dict[str, dict] = {}
    metrics_map: dict[str, dict] = {}

    if run_id:
        run_path = run_eval_summary_path(cfg, run_id)
        if run_path.exists():
            lift, metrics = read_eval_summary_file(run_path)
            merge_eval_maps(lift_map, metrics_map, lift, metrics)

    scoped_summary = (
        resolve_data_path(cfg, "algorithms", run_id=run_id) / "eval_summary.json"
    )
    if scoped_summary.exists():
        lift, metrics = read_eval_summary_file(scoped_summary)
        merge_eval_maps(lift_map, metrics_map, lift, metrics)

    global_summary = (
        get_data_root(cfg)
        / cfg.get("paths", {}).get("algorithms", "algorithms")
        / "eval_summary.json"
    )
    try:
        if global_summary.exists() and global_summary.resolve() != scoped_summary.resolve():
            lift, metrics = read_eval_summary_file(global_summary)
            merge_eval_maps(lift_map, metrics_map, lift, metrics)
    except OSError:
        pass

    seen: set[str] = set()
    for algo in algos or []:
        for key in algo_lookup_ids(algo):
            if key in seen:
                continue
            seen.add(key)
            m, lf = pick_eval_for_algo(lift_map, metrics_map, key)
            if lf and m:
                continue
            file_m, file_lf = load_per_algo_eval(cfg, key, run_id=run_id)
            register_eval_entry(
                lift_map,
                metrics_map,
                key,
                lift=file_lf or None,
                metrics=file_m or None,
            )

    return lift_map, metrics_map
