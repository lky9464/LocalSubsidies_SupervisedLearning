"""학습 파이프라인 (01~10, 추론 제외) + 분할/알고/누수 재개."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pandas as pd
import streamlit as st

from app.ui.common import (
    ALGO_LABELS,
    algo_multiselect,
    get_cfg,
    job_is_running,
    start_job,
)
from src.io.config import resolve_repo_path
from src.ops_db.repository import OpsRepository
from src.pipeline.run_config import (
    load_run_config,
    run_config_path,
    save_run_config,
    warn_test_share,
)
from src.pipeline.runner import TRAIN_PIPELINE_STEPS, new_run_id


def render() -> None:
    cfg = get_cfg()
    repo = OpsRepository(cfg)
    st.title("학습 파이프라인")
    st.caption("01~10 순차 (추론은 별도 메뉴). 실행은 백그라운드 Job으로 진행됩니다.")

    run_id = st.text_input("run_id", value=st.session_state.run_id)
    st.session_state.run_id = run_id
    if st.button("새 run_id 발급"):
        st.session_state.run_id = new_run_id()
        st.session_state.pop(f"opts_edit_{run_id}", None)
        st.rerun()

    run_cfg = load_run_config(cfg, run_id)
    step_map = _step_status_map(run_id)
    locked = _settings_locked(run_id, step_map)
    committed = bool(run_cfg.get("options_committed"))
    editing = bool(st.session_state.get(f"opts_edit_{run_id}", False))

    # 저장 완료 후 편집 UI 숨김 / 잠금 시 수정 불가
    show_editor = (not committed) or (editing and not locked)

    if show_editor:
        run_cfg = _render_options_editor(cfg, run_id, run_cfg, locked=False)
    else:
        _render_options_summary(run_cfg, locked=locked)
        if locked:
            st.caption(
                "1번 단계 시작 후~파이프라인 완료 전에는 학습 옵션을 변경할 수 없습니다."
            )
            if job_is_running():
                st.caption("실행 중인 Job은 상단 「Job 취소」로 전체 취소할 수 있습니다.")
            else:
                if st.button(
                    "전체 작업 취소 후 설정 수정",
                    key="opts_abandon",
                    help="진행 중이던 파이프라인 설정을 풀고 옵션을 다시 편집합니다.",
                ):
                    st.session_state[f"pipeline_abandon_{run_id}"] = True
                    st.session_state[f"opts_edit_{run_id}"] = True
                    st.rerun()
        else:
            if st.button("학습 옵션 수정", key="opts_reopen"):
                st.session_state[f"opts_edit_{run_id}"] = True
                st.rerun()

    algos = list(run_cfg.get("algorithms") or [])

    _leakage_remediation(cfg, run_id)

    st.subheader("단계별 실행")
    if not committed and not run_config_path(cfg, run_id).exists():
        st.info("먼저 「학습 옵션 저장」을 완료한 뒤 단계를 실행하세요.")

    if job_is_running():
        _steps_live(run_id, run_cfg, algos, committed)
    else:
        _render_step_buttons(run_id, run_cfg, algos, committed, step_map)

    st.subheader("일괄 실행 (01→10)")
    batch_disabled = (not committed) or job_is_running() or len(algos) < 2
    if st.button(
        "01→10 일괄 실행",
        type="primary",
        key="batch_open",
        disabled=batch_disabled,
    ):
        st.session_state["batch_dialog"] = True
        st.rerun()

    if st.session_state.get("batch_dialog"):
        _batch_dialog(cfg, run_id, run_cfg, algos)

    st.subheader("단계 상태")
    if job_is_running():
        _step_status_live(run_id)
    else:
        _render_step_status(run_id)


def _step_status_map(run_id: str) -> dict[str, str]:
    try:
        rows = OpsRepository(get_cfg()).list_steps(run_id)
    except Exception:  # noqa: BLE001
        return {}
    return {r["step_id"]: r.get("status", "") for r in rows}


def _settings_locked(run_id: str, step_map: dict[str, str]) -> bool:
    """
    1번 단계 시작 후 ~ 전체(01~10) 완료 전: 설정 잠금.
    해제: Job 취소 / 전체 작업 취소(설정 수정) / 전 단계 성공 / 실패 후 재시도.
    """
    if st.session_state.get(f"pipeline_abandon_{run_id}"):
        return False
    if job_is_running():
        return True

    statuses = [step_map.get(s["id"]) for s in TRAIN_PIPELINE_STEPS]
    relevant = [s for s in statuses if s]
    if not relevant:
        return False
    if any(s == "failed" for s in relevant):
        return False
    if all(step_map.get(s["id"]) == "succeeded" for s in TRAIN_PIPELINE_STEPS):
        return False
    # 한 단계라도 시작·성공했으면 완료 전까지 잠금
    return any(s in ("running", "succeeded") for s in relevant)


def _render_options_summary(run_cfg: dict, *, locked: bool) -> None:
    split = run_cfg.get("split") or {}
    mode = split.get("mode", "time")
    algos = run_cfg.get("algorithms") or []
    algo_txt = ", ".join(ALGO_LABELS.get(a, a) for a in algos) or "(없음)"
    if mode == "random":
        split_txt = f"랜덤 · test_size={split.get('test_size', 0.3)}"
    else:
        split_txt = (
            f"기간 · Train {split.get('train_start')}~{split.get('train_end')} / "
            f"Test {split.get('test_start')}~{split.get('test_end')}"
        )
    lock_tag = "🔒 잠금" if locked else "✓ 저장됨"
    st.markdown(
        f'<div class="lsl-card"><b>학습 옵션</b> ({lock_tag})<br/>'
        f"{split_txt}<br/>알고리즘: {algo_txt}</div>",
        unsafe_allow_html=True,
    )


def _render_options_editor(
    cfg: dict, run_id: str, run_cfg: dict, *, locked: bool
) -> dict[str, Any]:
    with st.expander("학습 옵션 (분할 · 알고리즘)", expanded=True):
        if locked:
            st.warning("현재 설정을 변경할 수 없습니다.")
            return run_cfg

        mode = st.radio(
            "분할 방식",
            ["time", "random"],
            index=0 if run_cfg.get("split", {}).get("mode", "time") == "time" else 1,
            format_func=lambda m: "기간(time)" if m == "time" else "랜덤(random)",
            horizontal=True,
        )
        split = dict(run_cfg.get("split") or {})
        split["mode"] = mode
        if mode == "time":
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(
                    '<div class="lsl-split-train"><p class="lsl-split-title">Train 기간</p></div>',
                    unsafe_allow_html=True,
                )
                with st.container(border=True):
                    split["train_start"] = st.text_input(
                        "Train 시작(YYYYMM)", split.get("train_start", "202401")
                    )
                    split["train_end"] = st.text_input(
                        "Train 종료", split.get("train_end", "202506")
                    )
            with c2:
                st.markdown(
                    '<div class="lsl-split-test"><p class="lsl-split-title">Test 기간</p></div>',
                    unsafe_allow_html=True,
                )
                with st.container(border=True):
                    split["test_start"] = st.text_input(
                        "Test 시작", split.get("test_start", "202507")
                    )
                    split["test_end"] = st.text_input(
                        "Test 종료", split.get("test_end", "202512")
                    )
            warn = warn_test_share(
                split["train_start"],
                split["train_end"],
                split["test_start"],
                split["test_end"],
            )
            if warn:
                st.warning(warn)
        else:
            split["test_size"] = st.slider(
                "Test 비중", 0.1, 0.5, float(split.get("test_size", 0.3)), 0.05
            )
            split["random_state"] = int(
                st.number_input("random_state", value=int(split.get("random_state", 42)))
            )

        algos = algo_multiselect(run_cfg.get("algorithms"))
        run_cfg["split"] = split
        run_cfg["algorithms"] = algos
        st.markdown('<div class="lsl-save-opts">', unsafe_allow_html=True)
        if st.button("학습 옵션 저장", type="primary", key="save_run_opts"):
            if len(algos) < 2:
                st.error("알고리즘을 2개 이상 선택하세요.")
            else:
                run_cfg["options_committed"] = True
                save_run_config(cfg, run_id, run_cfg)
                st.session_state[f"opts_edit_{run_id}"] = False
                st.success("학습 옵션이 저장되었습니다. 설정 화면을 숨깁니다.")
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    return run_cfg


@st.fragment(run_every=timedelta(seconds=2))
def _steps_live(
    run_id: str, run_cfg: dict, algos: list[str], committed: bool
) -> None:
    step_map = _step_status_map(run_id)
    _render_step_buttons(run_id, run_cfg, algos, committed, step_map)
    if not job_is_running():
        st.rerun()


def _render_step_buttons(
    run_id: str,
    run_cfg: dict,
    algos: list[str],
    committed: bool,
    step_map: dict[str, str],
) -> None:
    cfg = get_cfg()
    running = job_is_running()
    cols = st.columns(2)
    for i, step in enumerate(TRAIN_PIPELINE_STEPS):
        with cols[i % 2]:
            bcol, mcol = st.columns([5, 1])
            sid = step["id"]
            done = step_map.get(sid) == "succeeded"
            failed = step_map.get(sid) == "failed"
            with bcol:
                clicked = st.button(
                    step["label"],
                    key=f"step_{sid}",
                    disabled=(not committed) or running,
                    use_container_width=True,
                )
            with mcol:
                if done:
                    st.markdown(
                        '<p class="lsl-step-ok" title="완료">✅</p>',
                        unsafe_allow_html=True,
                    )
                elif failed:
                    st.markdown(
                        '<p class="lsl-step-fail" title="실패">❌</p>',
                        unsafe_allow_html=True,
                    )
                elif step_map.get(sid) == "running":
                    st.markdown(
                        '<p class="lsl-step-run" title="실행 중">⏳</p>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown('<p class="lsl-step-wait"> </p>', unsafe_allow_html=True)

            if clicked:
                # 단계 시작 시 설정 잠금 재적용 (이전에 잠금 해제한 경우)
                st.session_state[f"pipeline_abandon_{run_id}"] = False
                run_cfg = dict(run_cfg)
                run_cfg["options_committed"] = True
                save_run_config(cfg, run_id, run_cfg)
                if sid == "train" and len(algos) < 2:
                    st.error("학습 알고리즘을 2개 이상 선택하세요.")
                else:
                    start_job(
                        run_id,
                        [sid],
                        extra_args_by_step=_train_extra(sid, algos),
                    )


@st.fragment(run_every=timedelta(seconds=2))
def _step_status_live(run_id: str) -> None:
    st.caption("단계 상태 자동 갱신 중 (2초)")
    _render_step_status(run_id)
    if not job_is_running():
        st.rerun()


def _render_step_status(run_id: str) -> None:
    try:
        steps = OpsRepository(get_cfg()).list_steps(run_id)
        if steps:
            st.dataframe(pd.DataFrame(steps), use_container_width=True, hide_index=True)
        else:
            st.caption("아직 단계 기록이 없습니다. 단계를 실행하면 여기에 표시됩니다.")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"단계 상태 조회 일시 실패(Job 실행 중 DB 사용 중일 수 있음): {exc}")


def _batch_dialog(cfg: dict, run_id: str, run_cfg: dict, algos: list[str]) -> None:
    @st.dialog("일괄 실행 확인")
    def _dlg() -> None:
        st.warning(
            "일괄 실행은 수 분~수 시간이 걸릴 수 있습니다. "
            "절전을 끄고, 알고리즘 2개 이상·옵션 저장 후 진행하세요."
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("실행", type="primary", key="batch_run"):
                if len(algos) < 2:
                    st.error("알고리즘 2개 이상 필요")
                    return
                st.session_state[f"pipeline_abandon_{run_id}"] = False
                run_cfg["options_committed"] = True
                save_run_config(cfg, run_id, run_cfg)
                st.session_state["batch_dialog"] = False
                ids = [s["id"] for s in TRAIN_PIPELINE_STEPS]
                start_job(
                    run_id,
                    ids,
                    extra_args_by_step=_train_extra("train", algos),
                )
        with c2:
            if st.button("취소", key="batch_cancel"):
                st.session_state["batch_dialog"] = False
                st.rerun()

    _dlg()


def _train_extra(step_id: str, algos: list[str]) -> dict[str, list[str]] | None:
    if step_id != "train":
        return None
    args: list[str] = []
    for a in algos:
        args.extend(["--algo", a])
    return {"train": args} if args else None


def _leakage_remediation(cfg: dict, run_id: str) -> None:
    summary_path = resolve_repo_path(cfg, "reports_comparison") / "leakage_audit_summary.json"
    if not summary_path.exists():
        return
    try:
        with open(summary_path, encoding="utf-8") as f:
            meta = json.load(f)
    except OSError:
        return

    verdict = meta.get("verdict", "")
    suspects = list(meta.get("suspect_features") or [])
    forbidden = list(meta.get("forbidden_in_features") or [])
    if not (str(verdict).startswith("FAIL") or suspects or forbidden):
        return

    with st.expander("누수 점검 대응 (FAIL/WARN)", expanded=str(verdict).startswith("FAIL")):
        st.write(f"판정: **{verdict}**")
        features = sorted(set(forbidden + suspects))
        if features:
            st.write("의심·잔존 피처 (집계 목록):")
            st.code("\n".join(features[:40]))
        pick = st.multiselect("제외 목록에 추가할 피처", features, default=forbidden)
        if st.button("제외 반영 후 03부터 재개"):
            rc = load_run_config(cfg, run_id)
            extra = list(rc.get("exclude_features_extra") or [])
            for f in pick:
                if f not in extra:
                    extra.append(f)
            rc["exclude_features_extra"] = extra
            save_run_config(cfg, run_id, rc)
            OpsRepository(cfg).upsert_step(
                run_id,
                "leakage_remediation",
                "succeeded",
                message=f"제외 {len(pick)}개 후 03부터 재개: {', '.join(pick[:20])}",
                ended=True,
            )
            start_job(run_id, ["preprocess", "leakage"])
