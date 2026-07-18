"""추론 실행 + 결과 조회 (점검 우선순위표와 동일 주/보 구간 규칙)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from app.ui.common import ALGO_LABELS, get_cfg, start_job
from app.ui.inference_helpers import (
    available_inference_algos,
    export_inference_ops_queue,
    file_meta,
    inference_export_paths,
    inference_score_path,
    inference_top_xlsx_path,
    load_inference_queue,
    resolve_primary_aux,
)
from app.ui.matrix_view import render_inference_matrix
from src.io.config import get_data_root
from src.scoring.ops_queue import (
    BAND_HELP,
    CELL_COL,
    GRADE_COL,
    PRIMARY_LABELS,
    PRIORITY_COL,
    summarize_matrix,
    summarize_ops_queue,
)
from src.scoring.score_table import SCORE_COL


def _load_inference_csv(path, encoding: str) -> pd.DataFrame:
    return pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False)


def _render_run_section(cfg: dict, run_id: str) -> None:
    inf_dir = get_data_root(cfg) / "raw_inference"
    st.subheader("11 추론 실행")
    st.write("입력: `data_root/raw_inference/*.csv` (「데이터 등록」에서 업로드)")
    ignore = (cfg.get("inference") or {}).get("ignore_columns") or [
        "TAET_YN",
        "ISDP_RGSTR_YN",
        "ISRC_DSCL_YN",
        "PMBZ_CFMTN_YN",
    ]
    st.info(
        "추론 CSV 레이아웃은 학습·평가 raw와 동일합니다. "
        f"다음 컬럼은 사용하지 않으며 값이 있어도 무시됩니다: {', '.join(ignore)}"
    )

    exists = inf_dir.exists() and any(inf_dir.glob("*.csv"))
    if not exists:
        st.warning("raw_inference 에 CSV가 없습니다. 「데이터 등록」에서 추론 raw를 올려주세요.")
        st.button("11 추론 실행", disabled=True, key="infer_run_disabled")
        return

    opts = list(cfg.get("algorithms") or [])
    algos = st.multiselect(
        "실행할 알고리즘 (1개 이상)",
        options=opts,
        default=[a for a in opts if a in ("random_forest", "catboost") and a in opts],
        format_func=lambda a: ALGO_LABELS.get(a, a),
    )
    if st.button("11 추론 실행", type="primary", key="infer_run"):
        if len(algos) < 1:
            st.error("알고리즘을 1개 이상 선택하세요.")
            return
        args: list[str] = []
        for a in algos:
            args.extend(["--algo", a])
        start_job(run_id, ["inference"], extra_args_by_step={"inference": args})


def _render_export_section(cfg: dict, run_id: str) -> None:
    csv_path, xlsx_path = inference_export_paths(cfg)
    st.markdown("**점검 우선순위표 Excel 내보내기**")
    st.caption(
        "추론용 Excel: 전체 / 우선순위요약 / 4x4매트릭스(점검 선정) / 주A·주B·주C. "
        "평가용처럼 실제 양성 시트는 넣지 않습니다(타겟 미지)."
    )
    if csv_path.exists():
        meta = file_meta(csv_path)
        st.caption(f"기존 파일: `{csv_path}` · {meta['mtime']}")

    if st.button("점검 우선순위표 Excel 생성", type="secondary", key="infer_export"):
        try:
            out_csv, out_xlsx, n = export_inference_ops_queue(cfg, run_id)
            st.success(f"저장 완료 — {n:,}건")
            st.code(f"{out_csv}\n{out_xlsx}")
        except Exception as exc:  # noqa: BLE001
            st.error(str(exc))


def _render_results_section(cfg: dict, run_id: str) -> None:
    st.subheader("추론 결과")
    st.caption(
        "로컬 `scores/inference/{algo}_inference_scores.csv` · `_top.xlsx` "
        "(Test는 `scores/test/`, 동일 양식)를 읽어 주·보 구간·우선순위 집계와 미리보기를 표시합니다."
    )

    available = available_inference_algos(cfg)
    if not available:
        st.info("추론 결과 파일 없음 — 「추론 실행」에서 11 추론을 실행하세요.")
        primary = cfg.get("ops_queue", {}).get("primary_algo", "random_forest")
        st.caption(f"예상 경로: `{inference_score_path(cfg, primary)}`")
        return

    encoding = cfg.get("encoding", "EUC-KR")
    primary, aux = resolve_primary_aux(cfg, run_id)
    primary_path = inference_score_path(cfg, primary)
    aux_path = inference_score_path(cfg, aux)

    meta_rows = []
    for algo in available:
        p = inference_score_path(cfg, algo)
        m = file_meta(p)
        top_p = inference_top_xlsx_path(cfg, algo)
        meta_rows.append(
            {
                "알고리즘": ALGO_LABELS.get(algo, algo),
                "점수CSV": p.name,
                "상위Excel": "있음" if top_p.exists() else "없음",
                "갱신": m["mtime"],
                "크기(KB)": m["size_kb"],
            }
        )
    st.dataframe(pd.DataFrame(meta_rows), use_container_width=True, hide_index=True)

    _render_export_section(cfg, run_id)

    view = st.radio(
        "보기 방식",
        ["점검 우선순위 (주·보 4×4)", "알고리즘별 점수"],
        horizontal=True,
        key="infer_view_mode",
    )

    if view == "점검 우선순위 (주·보 4×4)":
        _render_grade_view(primary, aux, primary_path, aux_path, cfg, run_id, encoding)
    else:
        _render_algo_view(cfg, available, encoding)


def _render_grade_view(
    primary: str,
    aux: str,
    primary_path,
    aux_path,
    cfg: dict,
    run_id: str,
    encoding: str,
) -> None:
    if not primary_path.exists():
        st.warning(
            f"주 모델({ALGO_LABELS.get(primary, primary)}) 추론 결과가 없습니다."
        )
        return

    st.caption(
        f"주={ALGO_LABELS.get(primary, primary)} · "
        f"보조={ALGO_LABELS.get(aux, aux)} "
        + ("(보조 있음)" if aux_path.exists() else "(보조 없음 → 보D)")
    )

    g1, g2, g3, g4 = st.columns(4)
    g1.metric("주A", "상위1%", help=BAND_HELP["주A"])
    g2.metric("주B", "1~5%", help=BAND_HELP["주B"])
    g3.metric("주C", "5~10%", help=BAND_HELP["주C"])
    g4.metric("주D", ">10%", help=BAND_HELP["주D"])

    try:
        queue = load_inference_queue(cfg, run_id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"결과 로드 실패: {exc}")
        return
    if queue is None or queue.empty:
        st.write("집계 없음")
        return

    render_inference_matrix(summarize_matrix(queue))

    with st.expander("우선순위 집계 (1~16)", expanded=False):
        st.dataframe(summarize_ops_queue(queue), use_container_width=True, hide_index=True)

    grade = st.selectbox(
        "주등급 필터",
        [""] + list(PRIMARY_LABELS),
        format_func=lambda g: g if g else "(전체)",
        key="infer_grade_filter",
    )
    limit = st.slider("미리보기 행 수 (로컬만)", 0, 200, 30, 10, key="infer_preview_limit")

    if limit > 0:
        filtered = queue if not grade else queue[queue[GRADE_COL] == grade]
        preview = filtered.head(limit).copy()
        st.caption(
            f"미리보기 {len(preview):,}행 / 필터 후 {len(filtered):,}행 · "
            "전체는 「Excel 생성」 또는 로컬 CSV를 여세요."
            + (
                f" · 열: {PRIORITY_COL}, {CELL_COL}"
                if PRIORITY_COL in preview.columns
                else ""
            )
        )
        st.dataframe(preview, use_container_width=True, hide_index=True)


def _render_algo_view(cfg: dict, available: list[str], encoding: str) -> None:
    algo = st.selectbox(
        "알고리즘",
        available,
        format_func=lambda a: ALGO_LABELS.get(a, a),
        key="infer_algo_pick",
    )
    path = inference_score_path(cfg, algo)
    try:
        df = _load_inference_csv(path, encoding)
    except Exception as exc:  # noqa: BLE001
        st.error(f"읽기 실패: {exc}")
        return

    if SCORE_COL not in df.columns:
        st.error(f"점수 컬럼 `{SCORE_COL}` 이 없습니다.")
        return

    scores = pd.to_numeric(df[SCORE_COL], errors="coerce")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("행 수", f"{len(df):,}")
    c2.metric("평균 점수", f"{scores.mean():.1f}" if scores.notna().any() else "-")
    c3.metric("최고 점수", f"{int(scores.max())}" if scores.notna().any() else "-")
    c4.metric(
        "상위1% 추정",
        f"{max(1, int(round(len(df) * 0.01))):,}건"
        if len(df) > 0
        else "-",
    )

    if "CRTR_YM" in df.columns:
        ym = (
            df.groupby("CRTR_YM", dropna=False)
            .size()
            .reset_index(name="건수")
            .sort_values("CRTR_YM")
        )
        st.markdown("**기준연월별 건수**")
        st.dataframe(ym, use_container_width=True, hide_index=True)

    sort_high = st.checkbox("위험도 점수 내림차순", value=True, key="infer_sort_high")
    limit = st.slider("미리보기 행 수", 0, 200, 30, 10, key="infer_algo_limit")
    if limit > 0:
        show = df.copy()
        if sort_high:
            show["_sort"] = pd.to_numeric(show[SCORE_COL], errors="coerce")
            show = show.sort_values("_sort", ascending=False, kind="mergesort").drop(
                columns=["_sort"]
            )
        st.dataframe(show.head(limit), use_container_width=True, hide_index=True)


def render_run() -> None:
    """소메뉴: 추론 실행."""
    st.title("추론 실행")
    st.caption("학습 파이프라인과 분리된 독립 단계(11). 라벨 미지 데이터용.")
    cfg = get_cfg()
    run_id = st.session_state.run_id
    _render_run_section(cfg, run_id)


def render_results() -> None:
    """소메뉴: 결과 확인 (점검 우선순위표)."""
    st.title("결과 확인")
    st.caption("추론 점수·점검 우선순위표 조회 및 Excel 내보내기.")
    cfg = get_cfg()
    run_id = st.session_state.run_id
    _render_results_section(cfg, run_id)


def render() -> None:
    """하위 호환: 예전 단일 메뉴 진입 시 실행 화면."""
    render_run()
