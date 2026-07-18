"""Run 이력."""

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

    runs = repo.list_runs(50)
    if not runs:
        st.write("아직 run 기록이 없습니다.")
        return

    df = pd.DataFrame(runs)
    st.dataframe(df, use_container_width=True, hide_index=True)

    ids = [r["run_id"] for r in runs]
    pick = st.selectbox("Run 상세", ids, index=0)
    if st.button("이 Run을 현재로 설정"):
        st.session_state.run_id = pick
        st.success(f"현재 run = {pick}")

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
