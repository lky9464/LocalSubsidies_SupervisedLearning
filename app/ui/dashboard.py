"""대시보드 — 모델 평가 / 추론 섹션."""

from __future__ import annotations

import streamlit as st

from app.ui.common import ALGO_LABELS, get_cfg
from app.ui.inference_helpers import load_inference_queue, resolve_primary_aux
from app.ui.matrix_view import render_inference_matrix, render_test_dual_matrices
from app.ui.metrics_table import build_compare_frame
from src.ops_db.repository import OpsRepository
from src.pipeline.jobs import JobManager
from src.scoring.ops_queue import summarize_matrix


def render() -> None:
    cfg = get_cfg()
    repo = OpsRepository(cfg)
    run_id = st.session_state.run_id

    st.markdown(
        '<p class="lsl-brand">지방보조금 부정수급 위험도 측정</p>',
        unsafe_allow_html=True,
    )
    st.title("대시보드")
    st.caption("로컬 전용 · 127.0.0.1 · raw는 DB에 저장하지 않습니다.")

    c1, c2, c3 = st.columns(3)
    c1.metric("현재 Run", run_id)
    job = JobManager(cfg).get_active_job()
    if job and job.get("status") == "running":
        c2.metric("Job", "실행 중")
        c3.metric("진행", f"{int(float(job.get('progress') or 0) * 100)}%")
    else:
        c2.metric("Job", job.get("status") if job else "대기")
        c3.metric("최근 runs", str(len(repo.list_runs(5))))

    # ── 모델 평가 ──────────────────────────────────────────
    st.markdown("---")
    st.header("모델 평가")
    st.caption("학습·평가 파이프라인 결과 (Test).")

    ranking = repo.get_ranking(run_id)
    st.subheader("모델 순위")
    compare = build_compare_frame(cfg, ranking)
    if compare.empty:
        st.info(
            "순위 없음 — 학습 파이프라인에서 08 순위까지 실행후 표시됩니다."
        )
    else:
        st.dataframe(compare, use_container_width=True, hide_index=True)
        p, a = repo.get_primary_aux(run_id)
        st.success(f"주 모델={p} / 보조={a}")

    matrix_all, matrix_pos, meta = repo.ops_queue_matrices(run_id)
    if meta["total"] == 0:
        st.subheader("타겟 포착 분포")
        st.write("없음 — 10 타겟 포착 분포 실행 후 표시됩니다.")
    else:
        render_test_dual_matrices(matrix_all, matrix_pos, meta=meta)

    # ── 추론 ──────────────────────────────────────────────
    st.markdown("---")
    st.header("추론")
    st.caption(
        "라벨 미지 데이터 점검 우선순위 (주·보 4×4). "
        "상세·Excel은 「추론」→「결과 확인」."
    )

    primary, aux = resolve_primary_aux(cfg, run_id)
    st.caption(
        f"주={ALGO_LABELS.get(primary, primary)} · "
        f"보조={ALGO_LABELS.get(aux, aux)}"
    )

    try:
        queue = load_inference_queue(cfg, run_id)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"추론 집계 실패: {exc}")
        return

    if queue is None or queue.empty:
        st.write(
            "추론 결과 없음 — 「추론」→「추론 실행」 후 여기에 4×4가 표시됩니다."
        )
        return

    st.metric("추론 건수", f"{len(queue):,}")
    render_inference_matrix(summarize_matrix(queue))
