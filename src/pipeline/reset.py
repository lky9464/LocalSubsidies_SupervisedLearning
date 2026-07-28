"""Run-scoped pipeline reset: clear step history + artifacts from a step onward."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from src.io.config import get_data_root, resolve_data_path, run_workspace
from src.pipeline.runner import TRAIN_PIPELINE_STEPS

TRAIN_STEP_IDS_ORDERED: list[str] = [s["id"] for s in TRAIN_PIPELINE_STEPS]
TRAIN_STEP_INDEX: dict[str, int] = {sid: i for i, sid in enumerate(TRAIN_STEP_IDS_ORDERED)}


def earliest_step_id(step_ids: list[str]) -> str:
    """요청 step_ids 중 파이프라인 순서가 가장 앞인 id."""
    best: str | None = None
    best_i = 10**9
    for sid in step_ids:
        i = TRAIN_STEP_INDEX.get(sid)
        if i is not None and i < best_i:
            best_i = i
            best = sid
    if best is None:
        raise ValueError(f"알 수 없는 step_ids: {step_ids}")
    return best


def steps_from(from_step_id: str) -> list[str]:
    """from_step_id ~ ops_queue (포함)."""
    if from_step_id not in TRAIN_STEP_INDEX:
        raise ValueError(f"알 수 없는 단계: {from_step_id}")
    i = TRAIN_STEP_INDEX[from_step_id]
    return TRAIN_STEP_IDS_ORDERED[i:]


def _rm_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_file() or path.is_symlink():
        path.unlink(missing_ok=True)
    else:
        shutil.rmtree(path, ignore_errors=True)


def _clear_dir(path: Path) -> None:
    if not path.is_dir():
        return
    for child in list(path.iterdir()):
        _rm_path(child)


def delete_run_artifacts_from(
    cfg: dict[str, Any],
    run_id: str,
    from_step_id: str,
) -> dict[str, Any]:
    """
    Run 워크스페이스 파일 삭제 (outputs/reports 는 건드리지 않음).
    from_step_id 이후 단계에 해당하는 산출물만 제거.
    """
    ids = set(steps_from(from_step_id))
    ws = run_workspace(cfg, run_id)
    removed: list[str] = []
    if ws is None:
        return {"removed": removed}

    interim = resolve_data_path(cfg, "interim", run_id=run_id)
    processed = resolve_data_path(cfg, "processed", run_id=run_id)
    algorithms = resolve_data_path(cfg, "algorithms", run_id=run_id)
    reports = ws / "reports"

    if "merge" in ids or "label" in ids:
        # prep chain shares interim — wipe whole interim when any early prep resets
        if "merge" in ids:
            _clear_dir(interim)
            removed.append("interim/*")
        else:
            for name in ("labeled.csv",):
                p = interim / name
                if p.exists():
                    _rm_path(p)
                    removed.append(f"interim/{name}")

    if "preprocess" in ids or "merge" in ids or "label" in ids:
        if any(s in ids for s in ("merge", "label", "preprocess")):
            _clear_dir(processed)
            removed.append("processed/*")

    if "leakage" in ids or "merge" in ids or "label" in ids or "preprocess" in ids:
        if reports.is_dir():
            for name in (
                "leakage_audit.xlsx",
                "leakage_audit_summary.json",
            ):
                p = reports / name
                if p.exists():
                    _rm_path(p)
                    removed.append(f"reports/{name}")

    # train~ops: algorithms tree (includes inference scores)
    train_fwd = {
        "train",
        "feature_importance",
        "evaluate",
        "ranking",
        "report",
        "ops_queue",
    }
    if ids & train_fwd:
        if "train" in ids:
            _clear_dir(algorithms)
            removed.append("algorithms/*")
        else:
            # finer: keep models if only later steps — but if evaluate+, clear scores etc.
            if "feature_importance" in ids:
                for algo_dir in algorithms.glob("*"):
                    if not algo_dir.is_dir() or algo_dir.name == "operations":
                        continue
                    p = algo_dir / "feature_top10.json"
                    if p.exists():
                        _rm_path(p)
                        removed.append(f"algorithms/{algo_dir.name}/feature_top10.json")
            if "evaluate" in ids:
                for algo_dir in algorithms.glob("*"):
                    if not algo_dir.is_dir() or algo_dir.name == "operations":
                        continue
                    for rel in (
                        "eval_metrics.json",
                        "scores/test",
                    ):
                        p = algo_dir / rel
                        if p.exists():
                            _rm_path(p)
                            removed.append(f"algorithms/{algo_dir.name}/{rel}")
                for name in ("eval_summary.json",):
                    p = algorithms / name
                    if p.exists():
                        _rm_path(p)
                        removed.append(f"algorithms/{name}")
                snap = get_data_root(cfg) / "runs" / run_id / "eval_summary.json"
                if snap.exists():
                    _rm_path(snap)
                    removed.append("eval_summary.json")
            if "ranking" in ids:
                ops = algorithms / "operations"
                for name in ("model_ranking.json",):
                    p = ops / name
                    if p.exists():
                        _rm_path(p)
                        removed.append(f"algorithms/operations/{name}")
                snap = get_data_root(cfg) / "runs" / run_id / "eval_summary.json"
                if snap.exists():
                    _rm_path(snap)
                    removed.append("eval_summary.json")
            if "ops_queue" in ids:
                ops = algorithms / "operations"
                for name in (
                    "ops_queue_test.csv",
                    "ops_queue_test.xlsx",
                ):
                    p = ops / name
                    if p.exists():
                        _rm_path(p)
                        removed.append(f"algorithms/operations/{name}")

    # step logs for cleared steps
    logs = ws / "logs"
    if logs.is_dir():
        for sid in ids:
            p = logs / f"{sid}.log"
            if p.exists():
                _rm_path(p)
                removed.append(f"logs/{sid}.log")

    return {"removed": removed, "from_step": from_step_id, "step_ids": sorted(ids)}


def reset_pipeline_from(
    cfg: dict[str, Any],
    repo: Any,
    run_id: str,
    from_step_id: str,
) -> dict[str, Any]:
    """
    from_step_id ~ 10 단계 이력·DB·Run 산출물 삭제.
    취소 후 미실행으로 보이도록 run_steps 행을 제거한다.
    """
    step_ids = steps_from(from_step_id)
    repo.delete_steps(run_id, step_ids)

    # 08 ranking / 10 ops_queue DB — 해당 단계가 초기화 범위에 있으면 삭제
    if any(
        s in step_ids
        for s in ("train", "feature_importance", "evaluate", "ranking")
    ):
        repo.clear_ranking(run_id)
    if any(
        s in step_ids
        for s in (
            "train",
            "feature_importance",
            "evaluate",
            "ranking",
            "report",
            "ops_queue",
        )
    ):
        repo.clear_ops_queue(run_id)

    file_info = delete_run_artifacts_from(cfg, run_id, from_step_id)
    # Ensure workspace dirs exist for next run
    for key in ("interim", "processed", "algorithms"):
        resolve_data_path(cfg, key, run_id=run_id).mkdir(parents=True, exist_ok=True)
    (resolve_data_path(cfg, "algorithms", run_id=run_id) / "operations").mkdir(
        parents=True, exist_ok=True
    )
    reports = run_workspace(cfg, run_id)
    if reports is not None:
        (reports / "reports").mkdir(parents=True, exist_ok=True)
        (reports / "logs").mkdir(parents=True, exist_ok=True)

    return {
        "ok": True,
        "run_id": run_id,
        "from_step": from_step_id,
        "cleared_steps": step_ids,
        "files": file_info,
    }
