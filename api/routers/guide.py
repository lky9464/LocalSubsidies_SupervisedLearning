"""User guide documents."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from src.io.config import PROJECT_ROOT

router = APIRouter(prefix="/api/guide", tags=["guide"])

DOCS = PROJECT_ROOT / "docs"


@router.get("/intro")
def intro_md() -> PlainTextResponse:
    path = DOCS / "project_introduction.md"
    if not path.exists():
        raise HTTPException(404, "docs/project_introduction.md 가 없습니다.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


@router.get("/user")
def user_md() -> PlainTextResponse:
    path = DOCS / "user_guide.md"
    if not path.exists():
        raise HTTPException(404, "docs/user_guide.md 가 없습니다.")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown; charset=utf-8")


@router.get("/intro.pdf")
def intro_pdf():
    path = DOCS / "project_introduction.pdf"
    if not path.exists():
        raise HTTPException(404, "소개 PDF 없음")
    return FileResponse(path, filename="project_introduction.pdf", media_type="application/pdf")


@router.get("/user.pdf")
def user_pdf():
    path = DOCS / "user_guide.pdf"
    if not path.exists():
        raise HTTPException(404, "요약 PDF 없음")
    return FileResponse(path, filename="user_guide.pdf", media_type="application/pdf")


@router.post("/generate/intro")
def generate_intro() -> dict:
    try:
        from scripts.generate_introduction_pdf import main as build_intro  # type: ignore

        build_intro()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc
    return {"ok": True}


@router.post("/generate/user")
def generate_user() -> dict:
    try:
        from scripts.generate_user_guide_pdf import main as build_guide  # type: ignore

        build_guide()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc
    return {"ok": True}
