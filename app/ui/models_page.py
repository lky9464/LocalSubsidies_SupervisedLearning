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
    """선택 지표를 꼭짓점으로 하는 방사형(레이더) 차트 — 알고리즘별 색 구분."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        st.info("plotly 미설치 — `pip install plotly` 후 차트가 표시됩니다.")
        return

    st.subheader("비교 차트 (방사형)")
    st.caption(
        "선택한 지표가 꼭짓점이 됩니다. "
        "스케일이 다른 지표는 알고리즘 간 상대 비율(0~1)로 정규화해 비교합니다."
    )
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
    if len(pick) < 3:
        st.warning("방사형 차트는 지표를 3개 이상 선택하세요.")
        return

    # 지표별 min-max 정규화 (알고리즘 간 상대 비교)
    norm = df[pick].apply(pd.to_numeric, errors="coerce")
    for col in pick:
        lo = float(norm[col].min())
        hi = float(norm[col].max())
        if hi > lo:
            norm[col] = (norm[col] - lo) / (hi - lo)
        else:
            norm[col] = 1.0

    colors = [
        "#1565c0",  # blue
        "#c62828",  # red
        "#6a1b9a",  # purple
        "#ef6c00",  # orange
        "#00838f",  # teal
        "#2e7d32",  # green
        "#ad1457",  # pink
    ]
    theta = list(pick) + [pick[0]]

    fig = go.Figure()
    for i, (_, row) in enumerate(df.iterrows()):
        r_vals = [float(norm.loc[row.name, m]) for m in pick]
        r_vals.append(r_vals[0])
        color = colors[i % len(colors)]
        fig.add_trace(
            go.Scatterpolar(
                r=r_vals,
                theta=theta,
                name=str(row[label_col]),
                fill="toself",
                line=dict(color=color, width=2),
                fillcolor=color,
                opacity=0.45,
            )
        )

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1], tickfont=dict(size=10)),
            angularaxis=dict(tickfont=dict(size=11)),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.08, x=0),
        paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=40, r=40, t=60, b=40),
        height=520,
    )
    st.plotly_chart(fig, use_container_width=True)
