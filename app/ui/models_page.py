"""모델 비교·평가 — 지표·Plotly 차트 · Test 4×4(전체/양성)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui.common import get_cfg, start_job
from app.ui.matrix_view import render_test_dual_matrices
from app.ui.metrics_table import METRIC_HELP, build_compare_frame
from src.ops_db.repository import OpsRepository


def render() -> None:
    cfg = get_cfg()
    repo = OpsRepository(cfg)
    run_id = st.session_state.run_id
    st.title("모델 비교·평가")

    ranking = repo.get_ranking(run_id)
    compare = build_compare_frame(cfg, ranking)

    if compare.empty:
        st.warning("비교 데이터 없음 — 07 평가·08 순위 실행 후 확인하세요.")
    else:
        st.subheader("지표 표")
        with st.expander("지표 설명 (상위 N% 리프트·양성비중·양성포착)", expanded=False):
            st.markdown(
                f"- **상위N%리프트**: {METRIC_HELP['상위N%리프트']}\n"
                f"- **상위N%양성비중**: {METRIC_HELP['상위N%양성비중']}\n"
                f"- **상위N%양성포착**: {METRIC_HELP['상위N%양성포착']}"
            )
        st.dataframe(compare, use_container_width=True, hide_index=True)
        _charts_by_metric(compare)

    matrix_all, matrix_pos, meta = repo.ops_queue_matrices(run_id)
    if meta["total"] == 0:
        st.info(
            "Test 4×4 없음 — 07 평가 후 10 타겟 포착 분포를 실행하면 "
            "전체·실제 타겟 분포가 표시됩니다."
        )
    else:
        p, a = repo.get_primary_aux(run_id)
        st.caption(f"주·보 4×4 기준 모델: 주={p} / 보조={a}")
        render_test_dual_matrices(matrix_all, matrix_pos, meta=meta)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("08 모델 순위 재계산"):
            start_job(run_id, ["ranking"])
    with c2:
        if st.button("07 평가 재실행"):
            start_job(run_id, ["evaluate"])


def _charts_by_metric(df: pd.DataFrame) -> None:
    """지표별로 알고리즘을 나란히 비교."""
    try:
        import plotly.express as px
    except ImportError:
        st.info("plotly 미설치 — `pip install plotly` 후 차트가 표시됩니다.")
        return

    st.subheader("비교 차트")
    st.caption("같은 지표를 알고리즘 간에 비교합니다.")
    label_col = "알고리즘"
    metric_cols = [
        c
        for c in [
            "PR-AUC",
            "ROC-AUC",
            "F1",
            "상위1%리프트",
            "상위1%양성비중",
            "상위1%양성포착",
            "상위5%리프트",
            "상위5%양성비중",
            "상위5%양성포착",
        ]
        if c in df.columns
    ]
    if not metric_cols:
        return

    pick = st.multiselect(
        "표시할 지표",
        metric_cols,
        default=[m for m in metric_cols if m in ("PR-AUC", "상위1%리프트", "상위1%양성포착", "F1")],
    )
    if not pick:
        return

    melt = df.melt(
        id_vars=[label_col],
        value_vars=pick,
        var_name="지표",
        value_name="값",
    )
    # 지표별 facet — 각 지표에서 알고리즘 비교
    fig = px.bar(
        melt,
        x=label_col,
        y="값",
        color=label_col,
        facet_col="지표",
        facet_col_wrap=3,
        color_discrete_sequence=[
            "#1b5e4a",
            "#2e7d63",
            "#4caf8f",
            "#81c8b0",
            "#a8d5c4",
        ],
    )
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(l=10, r=10, t=40, b=80),
        height=280 * ((len(pick) + 2) // 3),
    )
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    # facet 기본은 맨 아랫줄만 x라벨 — 모든 패널에 알고리즘명 표시
    fig.for_each_xaxis(
        lambda ax: ax.update(showticklabels=True, tickangle=-35, title_text="")
    )
    fig.update_yaxes(matches=None, showticklabels=True)
    st.plotly_chart(fig, use_container_width=True)
