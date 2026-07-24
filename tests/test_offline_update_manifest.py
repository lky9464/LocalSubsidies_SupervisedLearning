"""offline_update_manifest.json sanity checks."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "offline_update_manifest.json"


def test_manifest_loads_and_release_matches_target() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = data["target_version"]
    releases = data["releases"]
    assert releases, "releases must not be empty"
    match = [r for r in releases if r["version"] == target]
    assert match, f"no release entry for target_version {target}"
    update_type = match[0]["update_type"]
    assert update_type in data["update_types"]


def test_preserve_includes_local_yaml() -> None:
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    preserve = data["preserve_always"]
    assert "configs/local.yaml" in preserve
    assert ".venv" in preserve
