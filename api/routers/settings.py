"""Settings."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_cfg, reload_cfg
from api.schemas.common import DataRootUpdate
from src.io.config import PROJECT_ROOT, get_data_root
from src.ops_db.db import get_ops_db_path, init_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings(cfg=Depends(get_cfg)) -> dict:
    try:
        data_root = str(get_data_root(cfg))
        db_path = str(get_ops_db_path(cfg))
    except ValueError:
        data_root = ""
        db_path = ""
    return {
        "data_root": data_root,
        "ops_db_basename": "ops.sqlite",
        "local_yaml_rel": "configs/local.yaml",
        "split_defaults": cfg.get("split", {}),
        "algorithms": cfg.get("algorithms", []),
        "has_data_root": bool(data_root),
    }


@router.put("/data-root")
def put_data_root(body: DataRootUpdate) -> dict:
    local_path = PROJECT_ROOT / "configs" / "local.yaml"
    example = PROJECT_ROOT / "configs" / "local.yaml.example"
    payload: dict = {}
    if local_path.exists():
        with open(local_path, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    elif example.exists():
        with open(example, encoding="utf-8") as f:
            payload = yaml.safe_load(f) or {}
    payload["data_root"] = body.data_root.strip()
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
    reload_cfg()
    return {"ok": True, "message": "저장됨. RunWebNext.bat 을 재시작하면 반영됩니다."}


@router.post("/db-init")
def db_init(cfg=Depends(get_cfg)) -> dict:
    try:
        path = init_db(cfg)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True, "message": f"준비됨: {path.name}"}
