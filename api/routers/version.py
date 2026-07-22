"""Version history from docs/VERSION_HISTORY.md."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.io.config import PROJECT_ROOT

router = APIRouter(prefix="/api/version", tags=["version"])

HISTORY_PATH = PROJECT_ROOT / "docs" / "VERSION_HISTORY.md"


def _parse_history(text: str) -> dict:
    current = ""
    m = re.search(r"현재\s*버전\s*:\s*\*\*(v?[\d.]+)\*\*", text)
    if m:
        current = m.group(1)
        if not current.startswith("v"):
            current = f"v{current}"

    entries: list[dict] = []
    # ## heading — optional title
    parts = re.split(r"(?m)^##\s+", text)
    for part in parts[1:]:
        lines = part.strip().splitlines()
        if not lines:
            continue
        head = lines[0].strip()
        # "v0.3.0 — Next.js..." or "Unreleased (...)"
        title = head
        version = head
        if "—" in head:
            version, _, title = head.partition("—")
            version = version.strip()
            title = title.strip()
        elif " - " in head:
            version, _, title = head.partition(" - ")
            version = version.strip()
            title = title.strip()

        bullets: list[str] = []
        release_url = ""
        for ln in lines[1:]:
            s = ln.strip()
            if not s or s == "---":
                continue
            if s.startswith("- "):
                bullets.append(s[2:].strip())
            elif s.startswith("* "):
                bullets.append(s[1:].strip().lstrip(" "))
            else:
                link = re.search(r"\((https?://[^)]+)\)", s)
                if link and ("Release" in s or "Tag" in s or "releases/tag" in s):
                    release_url = link.group(1)

        # skip pure meta intro without version-like heading
        if not version:
            continue
        entries.append(
            {
                "version": version,
                "title": title if title != version else "",
                "bullets": bullets,
                "release_url": release_url or None,
            }
        )

    released = [
        e
        for e in entries
        if re.match(r"^v?\d+\.\d+\.\d+", e["version"])
        and not re.match(r"^unreleased\b", e["version"], re.I)
    ]

    return {
        "current_version": current or (released[0]["version"] if released else ""),
        "entries": released,
        "source": "docs/VERSION_HISTORY.md",
    }


@router.get("")
def version_info() -> dict:
    path: Path = HISTORY_PATH
    if not path.is_file():
        raise HTTPException(404, "docs/VERSION_HISTORY.md 가 없습니다.")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(500, f"버전 문서 읽기 실패: {exc}") from exc
    return _parse_history(text)
