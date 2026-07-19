"""FastAPI dependency injection."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Generator

from src.io.config import load_config
from src.ops_db.db import init_db
from src.ops_db.repository import OpsRepository
from src.pipeline.jobs import JobManager


@lru_cache
def get_cfg() -> dict[str, Any]:
    cfg = load_config()
    try:
        init_db(cfg)
    except Exception:  # noqa: BLE001
        pass
    return cfg


def reload_cfg() -> dict[str, Any]:
    get_cfg.cache_clear()
    return get_cfg()


def get_repo() -> OpsRepository:
    return OpsRepository(get_cfg())


def get_job_manager() -> JobManager:
    return JobManager(get_cfg())


def cfg_dep() -> Generator[dict[str, Any], None, None]:
    yield get_cfg()
