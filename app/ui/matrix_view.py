"""주·보 4×4 매트릭스 표시 (Test 이중 / 추론 단일)."""

from __future__ import annotations

import pandas as pd
import streamlit as st


def render_test_dual_matrices(
    matrix_all: pd.DataFrame,
    matrix_pos: pd.DataFrame,
    *,
    meta: dict[str, int] | None = None,
) -> None:
    """
    (A) 평가 데이터 전체 4×4 · (B) 실제 타겟 분포 4×4.
    Test 평가용 — 점검 선정 UI가 아님.
    """
    total = int(meta["total"]) if meta and "total" in meta else int(matrix_all.to_numpy().sum())
    pos = (
        int(meta["positive"])
        if meta and "positive" in meta
        else int(matrix_pos.to_numpy().sum())
    )
    st.subheader("타겟 포착 4×4 — 전체 vs 실제 타겟")
    st.caption(
        "평가 구간은 이미 타겟이 확정된 데이터입니다. "
        "주·보조 모델이 실제 타겟을 어느 칸에 모았는지 비교합니다 "
        "(점검 대상 선정은 「추론」의 점검 우선순위표)."
    )
    m1, m2 = st.columns(2)
    m1.metric("평가 전체", f"{total:,}")
    m2.metric("실제 타겟=1", f"{pos:,}")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**(A) 평가 데이터 전체**")
        st.dataframe(matrix_all, use_container_width=True)
    with c2:
        h_l, h_r = st.columns([1, 1.4])
        with h_l:
            st.markdown("**(B) 실제 타겟 분포**")
        with h_r:
            st.markdown(
                '<p style="text-align:right;margin:0.35rem 0 0;'
                'font-size:0.85rem;color:rgba(49,51,63,0.6);">'
                "(A) 중 실제 타겟인 건의 분포</p>",
                unsafe_allow_html=True,
            )
        st.dataframe(matrix_pos, use_container_width=True)

    if pos > 0:
        top_bands = matrix_pos.loc[["주A", "주B", "주C"]].to_numpy().sum()
        pct = 100.0 * float(top_bands) / float(pos)
        st.caption(
            f"참고: 실제 양성 중 주A~주C에 모인 비율 ≈ {pct:.1f}% "
            f"({int(top_bands):,} / {pos:,})"
        )


def render_inference_matrix(matrix_all: pd.DataFrame) -> None:
    """추론용 — 점검 우선순위 선정을 위한 전체 4×4만."""
    st.subheader("4×4 매트릭스 (점검 선정용)")
    st.caption(
        "추론 데이터는 타겟을 알 수 없으므로, "
        "주·보 구간에 따른 점검 우선순위 분포만 표시합니다."
    )
    st.dataframe(matrix_all, use_container_width=True)
