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
    src = resolve_data_path(cfg, "algorithms") / "eval_summary.json"
    if not src.exists():
        return None
    dst = run_eval_summary_path(cfg, run_id)
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


def load_per_algo_eval(cfg: dict[str, Any], algo: str) -> tuple[dict, dict]:
    for key in algo_lookup_ids(algo):
        path = resolve_algo_dir(cfg, key) / "eval_metrics.json"
        if not path.exists():
            continue
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        return payload.get("metrics") or {}, payload.get("lift") or {}
    return {}, {}


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
    2) algorithms/eval_summary.json
    3) algorithms/{algo}/eval_metrics.json (alias·legacy 폴더 포함)
    """
    lift_map: dict[str, dict] = {}
    metrics_map: dict[str, dict] = {}

    if run_id:
        run_path = run_eval_summary_path(cfg, run_id)
        if run_path.exists():
            lift, metrics = read_eval_summary_file(run_path)
            merge_eval_maps(lift_map, metrics_map, lift, metrics)

    summary_path = resolve_data_path(cfg, "algorithms") / "eval_summary.json"
    if summary_path.exists():
        lift, metrics = read_eval_summary_file(summary_path)
        merge_eval_maps(lift_map, metrics_map, lift, metrics)

    seen: set[str] = set()
    for algo in algos or []:
        for key in algo_lookup_ids(algo):
            if key in seen:
                continue
            seen.add(key)
            m, lf = pick_eval_for_algo(lift_map, metrics_map, key)
            if lf and m:
                continue
            file_m, file_lf = load_per_algo_eval(cfg, key)
            register_eval_entry(
                lift_map,
                metrics_map,
                key,
                lift=file_lf or None,
                metrics=file_m or None,
            )

    return lift_map, metrics_map
