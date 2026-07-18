"""
로컬 전용 Streamlit 앱 (127.0.0.1만 사용).
실행: RunWeb.bat 또는 scripts/run_web.ps1
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.theme import inject_m3  # noqa: E402
from app.ui import (  # noqa: E402
    dashboard,
    data_page,
    guide_page,
    history_page,
    models_page,
    ops_page,
    pc_page,
    pipeline_page,
    settings_page,
)
from app.ui.common import ensure_session, get_cfg, render_job_banner  # noqa: E402
from app.ui.inference_page import render_results as infer_render_results  # noqa: E402
from app.ui.inference_page import render_run as infer_render_run  # noqa: E402
from src.ops_db.db import init_db  # noqa: E402

st.set_page_config(
    page_title="지방보조금 부정수급 위험도 측정",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 상위 메뉴 / 하위 메뉴 키
PAGE_DASH = "대시보드"
PAGE_DATA = "데이터 등록"
PAGE_PIPE = "학습 파이프라인"
PAGE_MODELS = "모델 비교·평가"
PAGE_OPS = "타겟 포착 분포"
PAGE_OPS_LEGACY = "점검 우선순위표"  # 구 학습메뉴명 → 자동 이전
PAGE_INFER_RUN = "추론 실행"
PAGE_INFER_RESULT = "결과 확인"
PAGE_INFER_LEGACY = "추론"  # 구 단일 메뉴 → 추론 실행
PAGE_HIST = "Run 이력"
PAGE_PC = "내 PC 사양 체크"
PAGE_GUIDE = "사용자 가이드"
PAGE_SET = "설정"

TRAIN_GROUP = {PAGE_PIPE, PAGE_MODELS, PAGE_OPS}
INFER_GROUP = {PAGE_INFER_RUN, PAGE_INFER_RESULT}


def _nav_button(label: str, page_key: str, *, indent: bool = False) -> None:
    active = st.session_state.page == page_key
    prefix = "· " if indent else ""
    typ = "primary" if active else "secondary"
    if st.sidebar.button(
        f"{prefix}{label}",
        key=f"nav_{page_key}",
        use_container_width=True,
        type=typ,
    ):
        st.session_state.page = page_key
        if page_key in TRAIN_GROUP:
            st.session_state.train_menu_open = True
        if page_key in INFER_GROUP:
            st.session_state.infer_menu_open = True
        st.rerun()


def _nav_group_toggle(label: str, open_key: str, btn_key: str) -> None:
    open_ = st.session_state[open_key]
    chevron = "▼" if open_ else "▶"
    if st.sidebar.button(
        f"{chevron} {label}",
        key=btn_key,
        use_container_width=True,
        type="secondary",
    ):
        st.session_state[open_key] = not open_
        st.rerun()


def render_sidebar_nav() -> str:
    if "page" not in st.session_state:
        st.session_state.page = PAGE_DASH
    # 구 세션 키 이전
    if st.session_state.page == PAGE_OPS_LEGACY:
        st.session_state.page = PAGE_OPS
    if st.session_state.page == PAGE_INFER_LEGACY:
        st.session_state.page = PAGE_INFER_RUN

    if "train_menu_open" not in st.session_state:
        st.session_state.train_menu_open = st.session_state.page in TRAIN_GROUP
    if "infer_menu_open" not in st.session_state:
        st.session_state.infer_menu_open = st.session_state.page in INFER_GROUP

    st.sidebar.markdown(
        '<p class="lsl-brand">지방보조금<br/>부정수급 위험도 측정</p>',
        unsafe_allow_html=True,
    )

    _nav_button(PAGE_DASH, PAGE_DASH)
    _nav_button(PAGE_DATA, PAGE_DATA)

    st.sidebar.markdown('<div class="lsl-nav-sep"></div>', unsafe_allow_html=True)
    _nav_group_toggle("모델 학습 및 평가", "train_menu_open", "nav_train_group")
    if st.session_state.train_menu_open:
        _nav_button(PAGE_PIPE, PAGE_PIPE, indent=True)
        _nav_button(PAGE_MODELS, PAGE_MODELS, indent=True)
        _nav_button(PAGE_OPS, PAGE_OPS, indent=True)

    st.sidebar.markdown('<div class="lsl-nav-sep"></div>', unsafe_allow_html=True)
    _nav_group_toggle("추론", "infer_menu_open", "nav_infer_group")
    if st.session_state.infer_menu_open:
        _nav_button(PAGE_INFER_RUN, PAGE_INFER_RUN, indent=True)
        _nav_button(PAGE_INFER_RESULT, PAGE_INFER_RESULT, indent=True)

    st.sidebar.markdown('<div class="lsl-nav-sep"></div>', unsafe_allow_html=True)
    _nav_button(PAGE_HIST, PAGE_HIST)
    _nav_button(PAGE_PC, PAGE_PC)
    _nav_button(PAGE_GUIDE, PAGE_GUIDE)
    _nav_button(PAGE_SET, PAGE_SET)

    st.sidebar.caption("bind: 127.0.0.1 · raw∉DB · Job 백그라운드")
    return st.session_state.page


def main() -> None:
    inject_m3()
    ensure_session()
    init_db(get_cfg())

    page = render_sidebar_nav()
    render_job_banner()

    if page == PAGE_DASH:
        dashboard.render()
    elif page == PAGE_DATA:
        data_page.render()
    elif page == PAGE_PIPE:
        pipeline_page.render()
    elif page == PAGE_MODELS:
        models_page.render()
    elif page == PAGE_OPS:
        ops_page.render()
    elif page == PAGE_INFER_RUN:
        infer_render_run()
    elif page == PAGE_INFER_RESULT:
        infer_render_results()
    elif page == PAGE_HIST:
        history_page.render()
    elif page == PAGE_PC:
        pc_page.render()
    elif page == PAGE_GUIDE:
        guide_page.render()
    else:
        settings_page.render()


if __name__ == "__main__":
    main()
