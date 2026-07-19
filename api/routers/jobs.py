"""Background jobs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_cfg, get_job_manager, get_repo
from api.schemas.common import JobCancel, JobStart
from api.services.pipeline import job_is_running
from api.state import set_pipeline_abandon
from src.pipeline.runner import STEP_BY_ID

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _job_payload(job: dict | None) -> dict | None:
    if not job:
        return None
    step_id = job.get("current_step")
    label = STEP_BY_ID.get(step_id, {}).get("label", step_id or "-")
    return {
        "job_id": job.get("job_id"),
        "run_id": job.get("run_id"),
        "status": job.get("status"),
        "current_step": step_id,
        "current_step_label": label,
        "progress": float(job.get("progress") or 0.0),
        "message": job.get("message") or "",
        "started_at": job.get("started_at"),
        "ended_at": job.get("ended_at"),
    }


@router.get("/active")
def active_job(mgr=Depends(get_job_manager)) -> dict:
    job = mgr.get_active_job(mutate=False)
    return {"job": _job_payload(job)}


@router.post("")
def start_job(body: JobStart, cfg=Depends(get_cfg), repo=Depends(get_repo), mgr=Depends(get_job_manager)) -> dict:
    if not body.run_id:
        raise HTTPException(400, "Run ID가 없습니다.")
    if not body.step_ids:
        raise HTTPException(400, "step_ids가 비어 있습니다.")
    try:
        repo.ensure_run(body.run_id)
        set_pipeline_abandon(cfg, body.run_id, False)
        job = mgr.start_steps(
            body.run_id,
            body.step_ids,
            extra_args_by_step=body.extra_args_by_step,
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, f"Job 시작 실패: {exc}") from exc
    return {"job": _job_payload(job)}


@router.post("/cancel")
def cancel_job(body: JobCancel, cfg=Depends(get_cfg), mgr=Depends(get_job_manager)) -> dict:
    try:
        job = mgr.cancel_job(body.job_id, body.run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc
    rid = job.get("run_id") if isinstance(job, dict) else body.run_id
    if rid and job.get("status") == "cancelled":
        set_pipeline_abandon(cfg, str(rid), True)
    return {"job": _job_payload(job) if isinstance(job, dict) else None}


@router.get("/running")
def is_running(cfg=Depends(get_cfg)) -> dict:
    return {"running": job_is_running(cfg)}
