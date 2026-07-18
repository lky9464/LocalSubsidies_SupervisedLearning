"""타겟 포착 분포 — Test 전체·양성 4×4. 점검 선정은 추론 메뉴."""

from __future__ import annotations

import streamlit as st

from app.ui.common import get_cfg, start_job
from app.ui.matrix_view import render_test_dual_matrices
from app.ui.metrics_table import format_ops_summary, sort_ops_summary_priority
from src.ops_db.repository import OpsRepository
from src.scoring.ops_queue import BAND_HELP, PRIMARY_LABELS


def render() -> None:
    cfg = get_cfg()
    repo = OpsRepository(cfg)
    run_id = st.session_state.run_id
    st.title("타겟 포착 분포")
    st.caption(
        "Test(평가) 구간: 주·보조가 실제 타겟을 어디에 모았는지 4×4로 봅니다. "
        "실제 점검 대상 선정은 「추론」 → 점검 우선순위표를 사용하세요."
    )

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("주A", "상위1%", help=BAND_HELP["주A"])
    g2.metric("주B", "1~5%", help=BAND_HELP["주B"])
    g3.metric("주C", "5~10%", help=BAND_HELP["주C"])
    g4.metric("주D", ">10%", help=BAND_HELP["주D"])

    matrix_all, matrix_pos, meta = repo.ops_queue_matrices(run_id)
    if meta["total"] == 0:
        st.write("데이터 없음 — 학습 파이프라인 10 타겟 포착 분포 실행 필요")
    else:
        render_test_dual_matrices(matrix_all, matrix_pos, meta=meta)

        with st.expander("조합별 건수·우선순위 (상세)", expanded=False):
            summary = sort_ops_summary_priority(repo.ops_queue_summary(run_id))
            st.dataframe(
                format_ops_summary(summary),
                use_container_width=True,
                hide_index=True,
            )

    grade = st.selectbox(
        "주등급 필터",
        [""] + list(PRIMARY_LABELS),
        format_func=lambda g: g if g else "(전체)",
        help="주등급별 의미는 상단 도움말을 참고하세요.",
    )
    limit = st.slider("미리보기 행 수 (로컬만)", 0, 200, 30, 10)
    if limit > 0 and meta["total"] > 0:
        df = repo.query_ops_queue(run_id, grade=grade or None, limit=limit)
        st.caption("행 미리보기는 제한됩니다. 전체는 로컬 Excel을 여세요.")
        st.dataframe(df, use_container_width=True, hide_index=True)

    if st.button("10 타겟 포착 분포 재실행", type="primary"):
        start_job(run_id, ["ops_queue"])
