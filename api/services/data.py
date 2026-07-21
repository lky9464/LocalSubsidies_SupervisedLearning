"""Raw data registration service."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from src.io.config import get_data_root, resolve_data_path


def count_lines(data: bytes, encoding: str) -> int | None:
    try:
        text = data.decode(encoding, errors="replace")
        return max(0, text.count("\n") - 1)
    except Exception:  # noqa: BLE001
        return None


def save_upload_files(
    cfg: dict[str, Any],
    repo: Any,
    files: list[tuple[str, bytes]],
    *,
    dataset_kind: str,
) -> int:
    if dataset_kind == "inference":
        target_dir = get_data_root(cfg) / "raw_inference"
        rel_prefix = "raw_inference"
    else:
        target_dir = resolve_data_path(cfg, "raw")
        rel_prefix = "raw"

    target_dir.mkdir(parents=True, exist_ok=True)
    encoding = cfg.get("encoding", "EUC-KR")

    for filename, _data in files:
        if repo.filename_exists(filename, dataset_kind=dataset_kind):
            raise ValueError(
                f"동일한 파일명이 이미 등록되어 있습니다: {filename}. "
                "이름을 바꾸거나 기존 파일을 삭제한 뒤 다시 등록하세요."
            )
        if (target_dir / filename).exists():
            raise ValueError(
                f"디스크에 동일 파일명이 있습니다: {filename}. "
                "이름을 바꾸거나 기존 파일을 삭제한 뒤 다시 등록하세요."
            )

    saved = 0
    for filename, data in files:
        path = target_dir / filename
        path.write_bytes(data)
        row_count = count_lines(data, encoding)
        sha = hashlib.sha256(data).hexdigest()
        repo.register_raw_file(
            filename,
            f"{rel_prefix}/{filename}",
            row_count=row_count,
            file_sha256=sha,
            note="web_upload",
            dataset_kind=dataset_kind,
            selected=True,
        )
        saved += 1
    return saved


def unlink_registry_rows(cfg: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    root = get_data_root(cfg)
    for row in rows:
        rel = row.get("rel_path")
        if not rel:
            continue
        p = root / str(rel)
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass
