"""Run CRUD."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_cfg, get_repo
from api.schemas.common import RunCreate
from api.state import set_current_run_id, set_opts_edit
from src.pipeline.runner import new_run_id

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _fmt_run(row: dict) -> dict:
    return {
        "run_id": row.get("run_id"),
        "created_at": row.get("created_at"),
        "operator": row.get("operator") or "",
        "work_content": row.get("work_content") or "",
        "note": row.get("note") or "",
        "status": row.get("status") or "",
    }


@router.get("")
def list_runs(limit: int = 30, repo=Depends(get_repo)) -> dict:
    rows = repo.list_runs(limit)
    return {"runs": [_fmt_run(r) for r in rows]}


@router.post("")
def create_run(body: RunCreate, cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    operator = body.operator.strip()
    work_content = body.work_content.strip()
    if not operator:
        raise HTTPException(400, "작업자를 입력하세요.")
    if not work_content:
        raise HTTPException(400, "작업내용을 입력하세요.")

    rid = new_run_id()
    repo.create_run(
        rid,
        operator=operator,
        work_content=work_content,
        note=body.note.strip(),
    )
    set_current_run_id(cfg, rid)
    set_opts_edit(cfg, rid, False)
    return {"run_id": rid}


@router.get("/{run_id}")
def get_run(run_id: str, repo=Depends(get_repo)) -> dict:
    rows = repo.list_runs(500)
    match = next((r for r in rows if r["run_id"] == run_id), None)
    if not match:
        raise HTTPException(404, "Run not found")
    return _fmt_run(match)
