"""대시보드 — Run 선택 카드 · 모델 평가 / 추론 섹션."""

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

    st.markdown(
        '<p class="lsl-brand">지방보조금 부정수급 위험도 측정</p>',
        unsafe_allow_html=True,
    )
    st.title("대시보드")
    st.caption("로컬 전용 · 127.0.0.1 · raw는 DB에 저장하지 않습니다.")

    _render_run_cards(repo)
    run_id = st.session_state.run_id

    job = JobManager(cfg).get_active_job()
    j1, j2 = st.columns(2)
    if job and job.get("status") == "running":
        j1.metric("Job", "실행 중")
        j2.metric("진행", f"{int(float(job.get('progress') or 0) * 100)}%")
    else:
        j1.metric("Job", job.get("status") if job else "대기")
        j2.metric("최근 runs", str(len(repo.list_runs(5))))

    # ── 모델 평가 ──────────────────────────────────────────
    st.markdown("---")
    st.header("모델 평가")
    st.caption(f"학습·평가 파이프라인 결과 (Test) · Run `{run_id}` 기준.")

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
        f"라벨 미지 데이터 점검 우선순위 (주·보 4×4) · Run `{run_id}` 기준. "
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


def _render_run_cards(repo: OpsRepository) -> None:
    """클릭으로 현재 Run 선택."""
    st.subheader("현재 Run 선택")
    runs = repo.list_runs(12)
    if not runs:
        st.info("Run 기록이 없습니다. 학습 파이프라인에서 새 Run을 시작하세요.")
        return

    current = st.session_state.run_id
    ids = {r["run_id"] for r in runs}
    if current not in ids:
        # 목록에 없으면 최신으로 맞춤
        st.session_state.run_id = runs[0]["run_id"]
        current = st.session_state.run_id

    st.markdown(
        f'<div class="lsl-run-hint">'
        f"<strong>선택됨:</strong> <code>{current}</code> — "
        f"아래 모델 평가·추론 및 다른 메뉴의 결과가 이 Run 기준으로 표시됩니다."
        f"</div>",
        unsafe_allow_html=True,
    )

    # 카드 그리드 (최대 4열)
    cols_per_row = 4
    for i in range(0, len(runs), cols_per_row):
        chunk = runs[i : i + cols_per_row]
        cols = st.columns(cols_per_row)
        for col, run in zip(cols, chunk):
            rid = run["run_id"]
            created = (run.get("created_at") or "")[:16].replace("T", " ")
            note = (run.get("note") or "").strip()
            active = rid == current
            label = f"{'● ' if active else ''}{rid}"
            with col:
                typ = "primary" if active else "secondary"
                if st.button(
                    label,
                    key=f"dash_run_{rid}",
                    use_container_width=True,
                    type=typ,
                    help=f"생성: {created}" + (f" · {note}" if note else ""),
                ):
                    if rid != st.session_state.run_id:
                        st.session_state.run_id = rid
                        st.rerun()
                st.caption(created or "—")
