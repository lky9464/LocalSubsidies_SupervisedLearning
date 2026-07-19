"""FastAPI application entry (127.0.0.1 only)."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from api.routers import (
    config,
    dashboard,
    data,
    guide,
    health,
    history,
    inference,
    jobs,
    models,
    ops,
    pipeline,
    runs,
    session,
    settings,
    system,
)
from src.io.config import PROJECT_ROOT

OUT_DIR = PROJECT_ROOT / "web" / "out"

app = FastAPI(title="Local Subsidies Web API", docs_url="/api/docs", redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8600",
        "http://localhost:8600",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for mod in (
    health,
    config,
    session,
    runs,
    jobs,
    pipeline,
    data,
    dashboard,
    models,
    ops,
    inference,
    history,
    system,
    settings,
    guide,
):
    app.include_router(mod.router)


class NextAssets(StaticFiles):
    """Hashed assets: long cache. RSC *.txt: correct content-type."""

    async def get_response(self, path: str, scope) -> Response:
        response = await super().get_response(path, scope)
        if path.endswith(".txt"):
            response.headers["content-type"] = "text/x-component; charset=utf-8"
        else:
            response.headers["cache-control"] = "public, max-age=31536000, immutable"
        return response


def _html_response(path: Path) -> FileResponse:
    return FileResponse(
        path,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


# Mount hashed Next assets before the SPA catch-all.
_assets = OUT_DIR / "_next"
if _assets.is_dir():
    app.mount("/_next", NextAssets(directory=str(_assets)), name="next-assets")


@app.get("/")
def root_page():
    index = OUT_DIR / "index.html"
    if index.is_file():
        return _html_response(index)
    return {"message": "API running. Build UI: scripts\\build_web.bat"}


@app.get("/{full_path:path}")
def spa_or_file(full_path: str):
    if full_path.startswith("api/") or full_path == "api":
        raise HTTPException(404)
    if full_path.startswith("_next/"):
        raise HTTPException(404)
    if not OUT_DIR.is_dir():
        raise HTTPException(404, "UI not built")

    candidate = OUT_DIR / full_path
    if candidate.is_file():
        if candidate.suffix.lower() in {".html", ".txt"}:
            headers = {"Cache-Control": "no-store"}
            media = (
                "text/x-component; charset=utf-8"
                if candidate.suffix.lower() == ".txt"
                else "text/html; charset=utf-8"
            )
            return FileResponse(candidate, media_type=media, headers=headers)
        return FileResponse(candidate)

    nested = OUT_DIR / full_path / "index.html"
    if nested.is_file():
        return _html_response(nested)

    index = OUT_DIR / "index.html"
    if index.is_file():
        return _html_response(index)
    raise HTTPException(404)
