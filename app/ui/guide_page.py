"""사용자 가이드 · 프로젝트 소개 PDF 다운로드."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]


def _download_button(path: Path, label: str, file_name: str, key: str) -> None:
    if not path.exists():
        return
    st.download_button(
        label,
        data=path.read_bytes(),
        file_name=file_name,
        mime="application/pdf",
        type="primary" if key == "intro" else "secondary",
        key=f"dl_{key}",
    )


def render() -> None:
    st.title("사용자 가이드")
    intro_md = ROOT / "docs" / "project_introduction.md"
    intro_pdf = ROOT / "docs" / "project_introduction.pdf"
    guide_md = ROOT / "docs" / "user_guide.md"
    guide_pdf = ROOT / "docs" / "user_guide.pdf"

    st.subheader("프로젝트 소개 (권장)")
    st.caption(
        "개발 목적 · 환경 구성 · raw 관리 · 업무 흐름 · 메뉴 설명 · 학습/추론 차이를 "
        "일반인 대상으로 정리한 문서입니다."
    )
    if intro_md.exists():
        with st.expander("소개 문서 미리보기 (Markdown)", expanded=False):
            st.markdown(intro_md.read_text(encoding="utf-8"))
    else:
        st.warning("docs/project_introduction.md 가 없습니다.")

    c1, c2 = st.columns(2)
    with c1:
        if intro_pdf.exists():
            _download_button(
                intro_pdf, "소개 PDF 다운로드", "project_introduction.pdf", "intro"
            )
        else:
            st.info(
                "소개 PDF 없음 — 로컬에서 "
                "`python scripts/generate_introduction_pdf.py` 실행"
            )
    with c2:
        if st.button("소개 PDF 생성", key="build_intro_pdf"):
            try:
                from scripts.generate_introduction_pdf import main as build_intro  # type: ignore

                build_intro()
                st.success("생성 완료")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(str(exc))

    st.divider()
    st.subheader("웹 조작 요약 (짧은 가이드)")
    if guide_md.exists():
        with st.expander("user_guide.md", expanded=False):
            st.markdown(guide_md.read_text(encoding="utf-8"))
    if guide_pdf.exists():
        _download_button(guide_pdf, "요약 PDF 다운로드", "user_guide.pdf", "guide")
    else:
        st.caption(
            "요약 PDF: `python scripts/generate_user_guide_pdf.py`"
        )
