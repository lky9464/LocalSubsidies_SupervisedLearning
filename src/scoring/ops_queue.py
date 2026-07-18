"""주/보 상위% 구간(A~D) 4×4 · 우선순위 1~16.

Test(10): 타겟 포착 분포 / 추론(11): 점검 우선순위표 — 동일 구간 규칙, 용도만 다름.
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import pandas as pd

from src.scoring.score_table import FIXED_SCORE_EXTRA_HEADERS, SCORE_COL

_ILLEGAL_EXCEL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# 열 이름
GRADE_COL = "주등급(primary_band)"  # 주A~주D
CB_GRADE_COL = "보등급(aux_band)"  # 보A~보D
CELL_COL = "조합(cell)"  # 주A×보A
PRIORITY_COL = "우선순위(priority)"  # 1~16
# 하위 호환 alias
CROSS_COL = CELL_COL

RF_SCORE_COL = "위험도점수_주모델(risk_score_primary)"
CB_SCORE_COL = "위험도점수_보조모델(risk_score_aux)"
PRED_COL = "예측라벨(predicted_label)"
ACTUAL_COL = "실제라벨(actual_label)"

BANDS = ("A", "B", "C", "D")
PRIMARY_LABELS = tuple(f"주{b}" for b in BANDS)
AUX_LABELS = tuple(f"보{b}" for b in BANDS)
PRIMARY_RANK = {f"주{b}": i for i, b in enumerate(BANDS)}
AUX_RANK = {f"보{b}": i for i, b in enumerate(BANDS)}

BAND_HELP = {
    "주A": "주모델 점수 상위 1% 이내 — 최우선",
    "주B": "주모델 상위 1% 초과~5% 이내",
    "주C": "주모델 상위 5% 초과~10% 이내",
    "주D": "주모델 상위 10% 초과 — 후순위",
    "보A": "보조모델 점수 상위 1% 이내",
    "보B": "보조모델 상위 1% 초과~5% 이내",
    "보C": "보조모델 상위 5% 초과~10% 이내",
    "보D": "보조모델 상위 10% 초과",
}


def _sanitize_excel_cell(value: Any) -> Any:
    if isinstance(value, str):
        return _ILLEGAL_EXCEL_RE.sub("", value)
    return value


def sanitize_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in out.columns:
        if out[col].dtype == object or pd.api.types.is_string_dtype(out[col]):
            out[col] = out[col].map(_sanitize_excel_cell)
    return out


def assign_percentile_bands(
    scores: pd.Series | np.ndarray,
    *,
    a_top_pct: float = 1.0,
    b_top_pct: float = 5.0,
    c_top_pct: float = 10.0,
    prefix: str = "",
) -> pd.Series:
    """
    상호 배타 구간 (점수 내림차순 순위 기준):
    - A: 상위 a% 이내
    - B: 상위 a% 초과 ~ b% 이내
    - C: 상위 b% 초과 ~ c% 이내
    - D: 상위 c% 초과
    prefix: '주' 또는 '보' → 주A, 보A …
    """
    s = pd.Series(np.asarray(scores, dtype=float), copy=False)
    n = len(s)
    if n == 0:
        return pd.Series([], index=s.index, dtype=object)

    vals = s.to_numpy(dtype=float)
    order = np.argsort(-vals, kind="mergesort")
    k_a = max(1, int(math.ceil(n * float(a_top_pct) / 100.0)))
    k_b = max(k_a, int(math.ceil(n * float(b_top_pct) / 100.0)))
    k_c = max(k_b, int(math.ceil(n * float(c_top_pct) / 100.0)))

    letters = np.full(n, "D", dtype=object)
    letters[order[:k_c]] = "C"
    letters[order[:k_b]] = "B"
    letters[order[:k_a]] = "A"
    if prefix:
        letters = np.array([f"{prefix}{x}" for x in letters], dtype=object)
    return pd.Series(letters, index=s.index, dtype=object)


def assign_grades(
    scores: pd.Series | np.ndarray,
    *,
    s_score_min: float = 900,  # noqa: ARG001 — 하위 호환(무시)
    a_top_pct: float = 1.0,
    b_top_pct: float = 5.0,
    c_top_pct: float = 10.0,
) -> pd.Series:
    """하위 호환: A~D 문자만 반환 (접두사 없음)."""
    return assign_percentile_bands(
        scores,
        a_top_pct=a_top_pct,
        b_top_pct=b_top_pct,
        c_top_pct=c_top_pct,
        prefix="",
    )


def priority_from_bands(primary: str, aux: str | None) -> int:
    """주등급×보등급 → 우선순위 1~16 (작을수록 우선)."""
    p = PRIMARY_RANK.get(str(primary), 3)
    a = AUX_RANK.get(str(aux or "보D"), 3)
    return int(p * 4 + a + 1)


def cell_label(primary: str, aux: str | None) -> str:
    return f"{primary}×{aux or '보D'}"


def _pick_existing(df: pd.DataFrame, cols: list[str]) -> list[str]:
    return [c for c in cols if c in df.columns]


def build_ops_queue(
    rf_df: pd.DataFrame,
    cb_df: pd.DataFrame | None,
    keys: list[str],
    ops_cfg: dict[str, Any],
) -> pd.DataFrame:
    """
    주·보조 점수표를 키로 조인하고 주/보 구간·우선순위를 부여한다.
    기여도 TOP10 열은 포함하지 않는다.
    """
    a_pct = float(ops_cfg.get("a_top_pct", 1))
    b_pct = float(ops_cfg.get("b_top_pct", 5))
    c_pct = float(ops_cfg.get("c_top_pct", 10))

    missing_keys = [k for k in keys if k not in rf_df.columns]
    if missing_keys:
        raise KeyError(f"주 모델 점수 파일에 키 컬럼 없음: {missing_keys}")
    if SCORE_COL not in rf_df.columns:
        raise KeyError(f"주 모델 점수 파일에 {SCORE_COL} 없음")

    fixed = _pick_existing(rf_df, FIXED_SCORE_EXTRA_HEADERS)
    label_cols = _pick_existing(rf_df, [PRED_COL, ACTUAL_COL])

    out = rf_df[keys + fixed].copy()
    out[RF_SCORE_COL] = pd.to_numeric(rf_df[SCORE_COL], errors="coerce")
    out[GRADE_COL] = assign_percentile_bands(
        out[RF_SCORE_COL],
        a_top_pct=a_pct,
        b_top_pct=b_pct,
        c_top_pct=c_pct,
        prefix="주",
    )

    out[CB_SCORE_COL] = np.nan
    out[CB_GRADE_COL] = "보D"

    if cb_df is not None and len(cb_df) > 0:
        cb_missing = [k for k in keys if k not in cb_df.columns]
        if cb_missing:
            raise KeyError(f"보조 모델 점수 파일에 키 컬럼 없음: {cb_missing}")
        if SCORE_COL not in cb_df.columns:
            raise KeyError(f"보조 모델 점수 파일에 {SCORE_COL} 없음")

        cb_part = cb_df[keys + [SCORE_COL]].copy()
        cb_part = cb_part.rename(columns={SCORE_COL: CB_SCORE_COL})
        cb_part[CB_SCORE_COL] = pd.to_numeric(cb_part[CB_SCORE_COL], errors="coerce")
        cb_part[CB_GRADE_COL] = assign_percentile_bands(
            cb_part[CB_SCORE_COL],
            a_top_pct=a_pct,
            b_top_pct=b_pct,
            c_top_pct=c_pct,
            prefix="보",
        )
        out = out.drop(columns=[CB_SCORE_COL, CB_GRADE_COL])
        out = out.merge(cb_part, on=keys, how="left", validate="one_to_one")
        out[CB_GRADE_COL] = out[CB_GRADE_COL].fillna("보D")

    out[CELL_COL] = [
        cell_label(p, a) for p, a in zip(out[GRADE_COL], out[CB_GRADE_COL])
    ]
    out[PRIORITY_COL] = [
        priority_from_bands(p, a)
        for p, a in zip(out[GRADE_COL], out[CB_GRADE_COL])
    ]

    for c in label_cols:
        out[c] = rf_df[c].values

    # 우선순위·점수 내림차순
    out = out.sort_values(
        [PRIORITY_COL, RF_SCORE_COL],
        ascending=[True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    ordered = (
        keys
        + fixed
        + [
            RF_SCORE_COL,
            CB_SCORE_COL,
            GRADE_COL,
            CB_GRADE_COL,
            CELL_COL,
            PRIORITY_COL,
        ]
        + label_cols
    )
    ordered = [c for c in ordered if c in out.columns]
    return out[ordered]


def summarize_ops_queue(queue_df: pd.DataFrame) -> pd.DataFrame:
    """주등급×보등급 4×4 집계 + 우선순위."""
    rows: list[dict[str, Any]] = []
    if GRADE_COL not in queue_df.columns:
        return pd.DataFrame(rows)

    for p in PRIMARY_LABELS:
        for a in AUX_LABELS:
            g = queue_df[(queue_df[GRADE_COL] == p) & (queue_df[CB_GRADE_COL] == a)]
            rows.append(
                {
                    "주등급": p,
                    "보등급": a,
                    "조합": cell_label(p, a),
                    "우선순위": priority_from_bands(p, a),
                    "건수(count)": int(len(g)),
                }
            )
    rows.append(
        {
            "주등급": "합계",
            "보등급": "",
            "조합": "",
            "우선순위": "",
            "건수(count)": int(len(queue_df)),
        }
    )
    return pd.DataFrame(rows)


def empty_band_matrix() -> pd.DataFrame:
    mat = pd.DataFrame(0, index=list(PRIMARY_LABELS), columns=list(AUX_LABELS))
    mat.index.name = "주＼보"
    return mat


def is_positive_label(values: pd.Series | np.ndarray | Any) -> pd.Series:
    """실제 타겟 양성(1) 판별. CSV·DB 문자열/수치 혼용 대응."""
    s = pd.Series(values)
    if s.empty:
        return pd.Series([], dtype=bool)
    # 수치 1
    num = pd.to_numeric(s, errors="coerce")
    as_num = num.eq(1)
    # 문자 Y/true 등
    text = s.astype(str).str.strip().str.lower()
    as_text = text.isin({"1", "1.0", "y", "yes", "true", "t"})
    return as_num.fillna(False) | as_text


def summarize_matrix(
    queue_df: pd.DataFrame,
    *,
    positive_only: bool = False,
    primary_col: str | None = None,
    aux_col: str | None = None,
    label_col: str | None = None,
) -> pd.DataFrame:
    """행=주등급, 열=보등급인 건수 매트릭스. positive_only면 실제 타겟=1만."""
    pcol = primary_col or GRADE_COL
    acol = aux_col or CB_GRADE_COL
    if queue_df is None or queue_df.empty or pcol not in queue_df.columns:
        return empty_band_matrix()

    df = queue_df
    if positive_only:
        lcol = label_col or ACTUAL_COL
        if lcol not in df.columns:
            return empty_band_matrix()
        df = df.loc[is_positive_label(df[lcol])]
        if df.empty:
            return empty_band_matrix()

    if acol not in df.columns:
        return empty_band_matrix()

    ct = df.groupby([pcol, acol], dropna=False).size().unstack(fill_value=0)
    ct = ct.reindex(index=list(PRIMARY_LABELS), columns=list(AUX_LABELS), fill_value=0)
    ct.index.name = "주＼보"
    return ct.astype(int)


def write_ops_queue_excel(
    queue_df: pd.DataFrame,
    out_path: Any,
    *,
    mode: str = "auto",
) -> None:
    """
    시트: 전체, 우선순위요약, 4×4, 주A~주C.
    mode:
      - test: 4x4전체 + 4x4실제양성 (평가·타겟 포착용)
      - inference: 4x4매트릭스만 (점검 선정용)
      - auto: 실제라벨 양성이 있으면 test, 없으면 inference
    """
    from pathlib import Path

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = sanitize_for_excel(queue_df)
    summary = summarize_ops_queue(clean)
    matrix_all = summarize_matrix(clean)

    has_pos = False
    if ACTUAL_COL in clean.columns:
        has_pos = bool(is_positive_label(clean[ACTUAL_COL]).any())
    use_test = mode == "test" or (mode == "auto" and has_pos)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        clean.to_excel(writer, sheet_name="전체", index=False)
        summary.to_excel(writer, sheet_name="우선순위요약", index=False)
        if use_test:
            matrix_all.to_excel(writer, sheet_name="4x4전체")
            summarize_matrix(clean, positive_only=True).to_excel(
                writer, sheet_name="4x4실제양성"
            )
        else:
            matrix_all.to_excel(writer, sheet_name="4x4매트릭스")
        for grade in ["주A", "주B", "주C"]:
            subset = clean[clean[GRADE_COL] == grade]
            subset.to_excel(writer, sheet_name=grade, index=False)
