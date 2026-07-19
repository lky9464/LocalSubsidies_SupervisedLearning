"""Run 이력 — 조회 전용 (현재 Run 선택은 대시보드)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui.common import get_cfg
from app.ui.matrix_view import render_test_dual_matrices
from app.ui.metrics_table import build_compare_frame
from src.ops_db.repository import OpsRepository


def render() -> None:
    cfg = get_cfg()
    repo = OpsRepository(cfg)
    st.title("Run 이력")
    st.caption(
        "조회 전용입니다. 웹 전반에 적용할 현재 Run은 "
        "「대시보드」의 Run 카드에서 선택하세요."
    )
    st.info(f"현재 적용 중 Run: `{st.session_state.run_id}`")

    runs = repo.list_runs(50)
    if not runs:
        st.write("아직 run 기록이 없습니다.")
        return

    df = pd.DataFrame(runs)
    st.dataframe(df, use_container_width=True, hide_index=True)

    ids = [r["run_id"] for r in runs]
    # 기본: 현재 run이 목록에 있으면 그것으로, 없으면 최신
    try:
        default_i = ids.index(st.session_state.run_id)
    except ValueError:
        default_i = 0
    pick = st.selectbox("상세 조회할 Run", ids, index=default_i)

    st.subheader("단계 상태")
    steps = repo.list_steps(pick)
    if steps:
        st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)
    else:
        st.write("단계 기록 없음")

    st.subheader("모델 순위")
    ranking = repo.get_ranking(pick)
    compare = build_compare_frame(cfg, ranking)
    if compare.empty:
        st.write("순위 없음")
    else:
        st.dataframe(compare, use_container_width=True, hide_index=True)

    matrix_all, matrix_pos, meta = repo.ops_queue_matrices(pick)
    if meta["total"] == 0:
        st.subheader("타겟 포착 분포")
        st.write("타겟 포착 분포 없음")
    else:
        render_test_dual_matrices(matrix_all, matrix_pos, meta=meta)
