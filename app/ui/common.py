"""공통 세션·배너·상수."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

import streamlit as st

from src.io.config import load_config
from src.models.factory import ALGORITHM_NAMES
from src.ops_db.repository import OpsRepository
from src.pipeline.jobs import JobManager
from src.pipeline.runner import STEP_BY_ID, new_run_id

ALGO_LABELS = {
    "catboost": "CatBoost",
    "stacked_ensemble": "Stacked Ensemble",
    "easy_ensemble": "EasyEnsemble",
    "gradient_boosting": "Gradient Boosting",
    "random_forest": "RandomForest",
}

# Job 배너 자동 갱신 주기
_JOB_POLL_SEC = 2


@st.cache_resource
def get_cfg() -> dict[str, Any]:
    return load_config()


def ensure_session() -> None:
    if "run_id" not in st.session_state:
        cfg = get_cfg()
        repo = OpsRepository(cfg)
        st.session_state.run_id = repo.get_latest_run_id() or new_run_id()


def peek_active_job() -> dict[str, Any] | None:
    """활성 Job 조회 (예외 삼킴)."""
    try:
        return JobManager(get_cfg()).get_active_job(mutate=False)
    except Exception:  # noqa: BLE001
        return None


def job_is_running(job: dict[str, Any] | None = None) -> bool:
    j = job if job is not None else peek_active_job()
    return bool(j and j.get("status") in ("running", "starting"))


def render_job_banner() -> dict[str, Any] | None:
    """
    전역 Job 배너.
    실행 중이면 fragment로 2초마다 자동 갱신 (수동 새로고침 불필요).
    """
    job = peek_active_job()
    if job_is_running(job):
        st.session_state["_job_live_active"] = True
        _job_banner_live()
        return job

    # 종료 직후: 라이브 폴링에서 넘어온 경우 한 번 전체 새로고침은 fragment 쪽에서 처리
    return _draw_job_banner(job, live=False)


@st.fragment(run_every=timedelta(seconds=_JOB_POLL_SEC))
def _job_banner_live() -> None:
    """실행 중 Job만 주기적으로 다시 그림."""
    job = peek_active_job()
    status = (job or {}).get("status", "unknown")

    if status in ("running", "starting"):
        _draw_job_banner(job, live=True)
        return

    # 완료/실패/취소로 바뀌면 전체 페이지를 한 번 갱신 (단계 상태 표 등)
    _draw_job_banner(job, live=False)
    if st.session_state.get("_job_live_active"):
        st.session_state["_job_live_active"] = False
        st.session_state["_job_just_finished"] = True
        st.rerun()


def _draw_job_banner(job: dict[str, Any] | None, *, live: bool) -> dict[str, Any] | None:
    if not job:
        return None

    cfg = get_cfg()
    mgr = JobManager(cfg)
    status = job.get("status", "unknown")
    step_id = job.get("current_step")
    label = STEP_BY_ID.get(step_id, {}).get("label", step_id or "-")
    prog = float(job.get("progress") or 0.0)
    pct = int(prog * 100)
    msg = job.get("message") or ""

    if status in ("running", "starting"):
        auto_note = f" · 자동 갱신 {_JOB_POLL_SEC}초" if live else ""
        st.markdown(
            f'<div class="lsl-banner">실행 중: {label} · 약 {pct}%{auto_note}'
            f' &nbsp;|&nbsp; run={job.get("run_id")} · job={job.get("job_id")}</div>',
            unsafe_allow_html=True,
        )
        st.progress(min(max(prog, 0.0), 1.0))
        c1, c2 = st.columns([4, 1])
        with c1:
            st.caption(msg or "백그라운드 실행 중 — 진행률이 자동으로 갱신됩니다.")
        with c2:
            if st.button("Job 취소", key="banner_cancel_job"):
                try:
                    mgr.cancel_job(job.get("job_id"), job.get("run_id"))
                    rid = job.get("run_id")
                    if rid:
                        st.session_state[f"pipeline_abandon_{rid}"] = True
                except Exception as exc:  # noqa: BLE001
                    st.error(str(exc))
                st.rerun()
    elif status == "succeeded":
        st.markdown(
            f'<div class="lsl-banner lsl-banner-ok">최근 Job 완료 · {job.get("run_id")}</div>',
            unsafe_allow_html=True,
        )
        if msg:
            st.caption(msg)
    elif status in ("failed", "cancelled"):
        st.markdown(
            f'<div class="lsl-banner lsl-banner-fail">최근 Job {status}: {msg[:200]}</div>',
            unsafe_allow_html=True,
        )
        if msg and len(msg) > 40:
            with st.expander("실패 로그 일부", expanded=True):
                st.code(msg)
    return job


def start_job(
    run_id: str,
    step_ids: list[str],
    *,
    extra_args_by_step: dict[str, list[str]] | None = None,
) -> None:
    cfg = get_cfg()
    mgr = JobManager(cfg)
    try:
        OpsRepository(cfg).ensure_run(run_id)
        job = mgr.start_steps(
            run_id, step_ids, extra_args_by_step=extra_args_by_step
        )
        st.session_state["last_started_job"] = job.get("job_id")
        st.session_state["_job_live_active"] = True
        st.success(
            f"백그라운드 Job 시작: {', '.join(step_ids)} "
            f"(job={job.get('job_id')}). 상단 배너가 자동으로 갱신됩니다."
        )
        time.sleep(0.2)
        st.rerun()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Job 시작 실패: {exc}")


def algo_multiselect(default: list[str] | None = None) -> list[str]:
    cfg = get_cfg()
    opts = list(cfg.get("algorithms") or ALGORITHM_NAMES)
    default = default if default is not None else opts
    selected = st.multiselect(
        "학습 알고리즘 (2개 이상)",
        options=opts,
        default=[a for a in default if a in opts],
        format_func=lambda a: ALGO_LABELS.get(a, a),
    )
    return selected
