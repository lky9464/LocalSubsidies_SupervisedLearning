"""Next UI + FastAPI smoke test (no raw/score row dumps).

Usage (server already on :8600):
  .venv\\Scripts\\python.exe scripts\\smoke_web_ui.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any

BASE = "http://127.0.0.1:8600"
TIMEOUT = 15

PAGES = [
    "/",
    "/run-issue/",
    "/data/",
    "/pipeline/",
    "/models/",
    "/ops/",
    "/inference/run/",
    "/inference/results/",
    "/history/",
    "/pc/",
    "/guide/",
    "/settings/",
]


def fetch(path: str, method: str = "GET", body: dict | None = None) -> tuple[int, Any, str]:
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            ctype = resp.headers.get("Content-Type", "")
            if "application/json" in ctype or path.startswith("/api/"):
                try:
                    return resp.status, json.loads(raw.decode("utf-8")), ctype
                except json.JSONDecodeError:
                    return resp.status, raw[:200], ctype
            return resp.status, f"<html len={len(raw)}>", ctype
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:300].decode("utf-8", errors="replace"), ""
    except Exception as e:  # noqa: BLE001
        return 0, str(e), ""


def ok(status: int) -> bool:
    return 200 <= status < 400


def main() -> int:
    fails: list[str] = []
    print(f"Smoke against {BASE}\n")

    st, health, _ = fetch("/api/health")
    print(f"[API] /api/health -> {st} {health}")
    if not ok(st):
        print("Server not reachable. Start RunWebNext.bat first.")
        return 2

    print("\n== Static pages ==")
    for p in PAGES:
        st, body, ctype = fetch(p)
        mark = "OK" if ok(st) and "html" in ctype else "FAIL"
        if mark == "FAIL":
            fails.append(f"page {p} status={st} ctype={ctype} body={body!r:.80}")
        print(f"  [{mark}] {p} -> {st} {ctype}")

    print("\n== Core APIs ==")
    st, runs_payload, _ = fetch("/api/runs?limit=5")
    print(f"  [{'OK' if ok(st) else 'FAIL'}] /api/runs -> {st}")
    if not ok(st):
        fails.append(f"/api/runs {st}")
        runs: list[dict] = []
    else:
        runs = list((runs_payload or {}).get("runs") or [])

    st, cur, _ = fetch("/api/session/current-run")
    print(f"  [{'OK' if ok(st) else 'FAIL'}] /api/session/current-run -> {st}")
    if not ok(st):
        fails.append("current-run")

    st, job, _ = fetch("/api/jobs/active")
    print(f"  [{'OK' if ok(st) else 'FAIL'}] /api/jobs/active -> {st}")
    if not ok(st):
        fails.append("jobs/active")

    st, meta, _ = fetch("/api/config/meta")
    print(f"  [{'OK' if ok(st) else 'FAIL'}] /api/config/meta -> {st}")
    if not ok(st):
        fails.append("config/meta")

    for path in ("/api/data/raw", "/api/data/raw-inference"):
        st, payload, _ = fetch(path)
        n = len((payload or {}).get("items") or []) if isinstance(payload, dict) else "?"
        mark = "OK" if ok(st) else "FAIL"
        if mark == "FAIL":
            fails.append(path)
        print(f"  [{mark}] {path} -> {st} items={n}")

    for path in ("/api/system/pc", "/api/settings", "/api/guide/intro", "/api/inference/prereq"):
        st, _, _ = fetch(path)
        mark = "OK" if st in (200, 404) or ok(st) else "FAIL"
        if mark == "FAIL":
            fails.append(path)
        print(f"  [{mark}] {path} -> {st}")

    rid = ""
    if isinstance(cur, dict):
        rid = str(cur.get("run_id") or "")
    if not rid and runs:
        rid = str(runs[0].get("run_id") or "")

    if rid:
        print(f"\n== Run-scoped APIs (run_id={rid}) ==")
        for path in (
            f"/api/runs/{rid}/dashboard",
            f"/api/runs/{rid}/config",
            f"/api/runs/{rid}/steps",
            f"/api/runs/{rid}/leakage",
            f"/api/runs/{rid}/models",
            f"/api/runs/{rid}/ops-queue",
            f"/api/runs/{rid}/history",
            f"/api/inference/results?run_id={rid}",
            f"/api/inference/ops-queue?run_id={rid}&limit=10",
        ):
            st, payload, _ = fetch(path)
            mark = "OK" if ok(st) or st == 404 else "FAIL"
            if mark == "FAIL":
                fails.append(f"{path} -> {st} {payload!r:.120}")
            extra = ""
            if isinstance(payload, dict) and "ranking_empty" in payload:
                extra = f" ranking_empty={payload.get('ranking_empty')}"
            if isinstance(payload, dict) and "empty" in payload:
                extra += f" empty={payload.get('empty')}"
            print(f"  [{mark}] {path} -> {st}{extra}")
    else:
        print("\n(no run_id — skip run-scoped APIs)")

    print("\n== Summary ==")
    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails:
            print(f"  - {f}")
        return 1
    print("PASS - all smoke checks ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
