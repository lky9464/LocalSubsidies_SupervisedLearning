"""Pydantic schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    operator: str = Field(..., min_length=1)
    work_content: str = Field(..., min_length=1)
    note: str = ""


class RunOut(BaseModel):
    run_id: str
    created_at: str | None = None
    operator: str | None = None
    work_content: str | None = None
    note: str | None = None
    status: str | None = None


class CurrentRunUpdate(BaseModel):
    run_id: str


class JobStart(BaseModel):
    run_id: str
    step_ids: list[str]
    extra_args_by_step: dict[str, list[str]] | None = None


class JobCancel(BaseModel):
    job_id: str | None = None
    run_id: str | None = None


class RunConfigUpdate(BaseModel):
    split: dict[str, Any] | None = None
    algorithms: list[str] | None = None
    options_committed: bool | None = None
    exclude_features_extra: list[str] | None = None


class PipelineAbandonUpdate(BaseModel):
    abandon: bool = True
    opts_edit: bool = True


class DataRootUpdate(BaseModel):
    data_root: str = Field(..., min_length=1)


class LeakageResume(BaseModel):
    features: list[str] = Field(default_factory=list)
