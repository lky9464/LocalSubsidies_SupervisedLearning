"""Current run session."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_cfg, get_repo
from api.schemas.common import CurrentRunUpdate
from api.state import get_current_run_id, set_current_run_id

router = APIRouter(prefix="/api/session", tags=["session"])


@router.get("/current-run")
def get_current_run(cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    run_id = get_current_run_id(cfg)
    if not run_id:
        run_id = repo.get_latest_run_id() or ""
        if run_id:
            set_current_run_id(cfg, run_id)
    return {"run_id": run_id}


@router.put("/current-run")
def put_current_run(body: CurrentRunUpdate, cfg=Depends(get_cfg)) -> dict:
    set_current_run_id(cfg, body.run_id)
    return {"run_id": body.run_id}
