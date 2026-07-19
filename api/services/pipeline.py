"""Pipeline lock FSM and step helpers."""

from __future__ import annotations

from typing import Any

from api.state import get_pipeline_abandon
from src.pipeline.jobs import JobManager
from src.pipeline.runner import TRAIN_PIPELINE_STEPS


def step_status_map(repo: Any, run_id: str) -> dict[str, str]:
    try:
        rows = repo.list_steps(run_id)
    except Exception:  # noqa: BLE001
        return {}
    return {r["step_id"]: r.get("status", "") for r in rows}


def job_is_running(cfg: dict[str, Any]) -> bool:
    try:
        job = JobManager(cfg).get_active_job(mutate=False)
    except Exception:  # noqa: BLE001
        return False
    return bool(job and job.get("status") in ("running", "starting"))


def settings_locked(cfg: dict[str, Any], run_id: str, step_map: dict[str, str]) -> bool:
    if get_pipeline_abandon(cfg, run_id):
        return False
    if job_is_running(cfg):
        return True

    statuses = [step_map.get(s["id"]) for s in TRAIN_PIPELINE_STEPS]
    relevant = [s for s in statuses if s]
    if not relevant:
        return False
    if any(s == "failed" for s in relevant):
        return False
    if all(step_map.get(s["id"]) == "succeeded" for s in TRAIN_PIPELINE_STEPS):
        return False
    return any(s in ("running", "succeeded") for s in relevant)


def extra_for_steps(step_ids: list[str], algos: list[str]) -> dict[str, list[str]] | None:
    if "train" not in step_ids:
        return None
    args: list[str] = []
    for a in algos:
        args.extend(["--algo", a])
    return {"train": args} if args else None
