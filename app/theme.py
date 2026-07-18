"""Streamlit에 M3 유사 CSS 주입."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

_CSS = Path(__file__).resolve().parent / "styles" / "m3.css"


def inject_m3() -> None:
    if not _CSS.exists():
        return
    css = _CSS.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
