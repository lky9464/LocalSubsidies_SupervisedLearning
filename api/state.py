"""Server-side session state files under {data_root}/runs/."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from src.io.config import get_data_root


def _runs_dir(cfg: dict[str, Any]) -> Path:
    d = get_data_root(cfg) / "runs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(0.05)
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        return {}


def current_run_path(cfg: dict[str, Any]) -> Path:
    return _runs_dir(cfg) / "_current_run.json"


def pipeline_state_path(cfg: dict[str, Any]) -> Path:
    return _runs_dir(cfg) / "_pipeline_state.json"


def get_current_run_id(cfg: dict[str, Any]) -> str:
    data = _read_json(current_run_path(cfg))
    return str(data.get("run_id") or "")


def set_current_run_id(cfg: dict[str, Any], run_id: str) -> None:
    _atomic_write_json(current_run_path(cfg), {"run_id": run_id})


def get_pipeline_abandon(cfg: dict[str, Any], run_id: str) -> bool:
    data = _read_json(pipeline_state_path(cfg))
    return bool(data.get("abandon", {}).get(run_id))


def set_pipeline_abandon(cfg: dict[str, Any], run_id: str, value: bool) -> None:
    path = pipeline_state_path(cfg)
    data = _read_json(path)
    abandon = dict(data.get("abandon") or {})
    if value:
        abandon[run_id] = True
    else:
        abandon.pop(run_id, None)
    data["abandon"] = abandon
    _atomic_write_json(path, data)


def get_opts_edit(cfg: dict[str, Any], run_id: str) -> bool:
    data = _read_json(pipeline_state_path(cfg))
    return bool(data.get("opts_edit", {}).get(run_id))


def set_opts_edit(cfg: dict[str, Any], run_id: str, value: bool) -> None:
    path = pipeline_state_path(cfg)
    data = _read_json(path)
    opts_edit = dict(data.get("opts_edit") or {})
    if value:
        opts_edit[run_id] = True
    else:
        opts_edit.pop(run_id, None)
    data["opts_edit"] = opts_edit
    _atomic_write_json(path, data)
