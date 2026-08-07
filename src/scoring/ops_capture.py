"""Test 타겟 포착 분포 — 3케이스(PK·엔티티) pair queue · 4×4.

`ops_queue.py`의 percentile·양성 판별을 재사용. 추론(11)은 기존 build_ops_queue 유지.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.scoring.ops_queue import (
    ACTUAL_COL,
    BANDS,
    CELL_COL,
    CB_GRADE_COL,
    CB_SCORE_COL,
    GRADE_COL,
    PRED_COL,
    PRIORITY_COL,
    RF_SCORE_COL,
    SCORE_COL,
    assign_percentile_bands,
    cell_label,
    is_positive_label,
    sanitize_for_excel,
    summarize_matrix,
    _pick_existing,
)
from src.scoring.score_table import FIXED_SCORE_EXTRA_HEADERS

CASE_PRIMARY_AUX = "primary_aux"
CASE_PRIMARY_REF = "primary_reference"
CASE_AUX_REF = "aux_reference"

REF_GRADE_COL = "참등급(reference_band)"
REF_SCORE_COL = "위험도점수_참모델(risk_score_reference)"
CASE_ID_COL = "케이스(case_id)"

ENTITY_KEY_DEFAULT = ("PFM_BIZ_ID", "INST_ID")


@dataclass(frozen=True)
class OpsPairSpec:
    case_id: str
    title: str
    row_prefix: str
    col_prefix: str
    row_grade_col: str
    col_grade_col: str
    row_score_col: str
    col_score_col: str

    @property
    def row_labels(self) -> tuple[str, ...]:
        return tuple(f"{self.row_prefix}{b}" for b in BANDS)

    @property
    def col_labels(self) -> tuple[str, ...]:
        return tuple(f"{self.col_prefix}{b}" for b in BANDS)

    @property
    def matrix_index_name(self) -> str:
        return f"{self.row_prefix}＼{self.col_prefix}"


OPS_PAIR_SPECS: tuple[OpsPairSpec, ...] = (
    OpsPairSpec(
        case_id=CASE_PRIMARY_AUX,
        title="주 / 보",
        row_prefix="주",
        col_prefix="보",
        row_grade_col=GRADE_COL,
        col_grade_col=CB_GRADE_COL,
        row_score_col=RF_SCORE_COL,
        col_score_col=CB_SCORE_COL,
    ),
    OpsPairSpec(
        case_id=CASE_PRIMARY_REF,
        title="주 / 참",
        row_prefix="주",
        col_prefix="참",
        row_grade_col=GRADE_COL,
        col_grade_col=REF_GRADE_COL,
        row_score_col=RF_SCORE_COL,
        col_score_col=REF_SCORE_COL,
    ),
    OpsPairSpec(
        case_id=CASE_AUX_REF,
        title="보 / 참",
        row_prefix="보",
        col_prefix="참",
        row_grade_col=CB_GRADE_COL,
        col_grade_col=REF_GRADE_COL,
        row_score_col=CB_SCORE_COL,
        col_score_col=REF_SCORE_COL,
    ),
)

BAND_HELP_REF = {
    f"참{b}": {
        "A": "참조 모델 점수 상위 1% 이내",
        "B": "참조 모델 상위 1% 초과~5% 이내",
        "C": "참조 모델 상위 5% 초과~10% 이내",
        "D": "참조 모델 상위 10% 초과",
    }[b]
    for b in BANDS
}


def parse_entity_keys(cfg: dict[str, Any]) -> tuple[str, ...]:
    raw = str((cfg.get("split") or {}).get("group_key") or "PFM_BIZ_ID+INST_ID")
    parts = [p.strip() for p in raw.split("+") if p.strip()]
    return tuple(parts) if parts else ENTITY_KEY_DEFAULT


def priority_from_pair(row_band: str, col_band: str, spec: OpsPairSpec) -> int:
    row_rank = {lb: i for i, lb in enumerate(spec.row_labels)}
    col_rank = {lb: i for i, lb in enumerate(spec.col_labels)}
    p = row_rank.get(str(row_band), len(spec.row_labels) - 1)
    c = col_rank.get(str(col_band), len(spec.col_labels) - 1)
    return int(p * len(spec.col_labels) + c + 1)


def empty_band_matrix_for(spec: OpsPairSpec) -> pd.DataFrame:
    mat = pd.DataFrame(0, index=list(spec.row_labels), columns=list(spec.col_labels))
    mat.index.name = spec.matrix_index_name
    return mat


def summarize_matrix_for(
    queue_df: pd.DataFrame,
    spec: OpsPairSpec,
    *,
    positive_only: bool = False,
    label_col: str | None = None,
) -> pd.DataFrame:
    pcol = spec.row_grade_col
    acol = spec.col_grade_col
    if queue_df is None or queue_df.empty or pcol not in queue_df.columns:
        return empty_band_matrix_for(spec)

    df = queue_df
    if positive_only:
        lcol = label_col or ACTUAL_COL
        if lcol not in df.columns:
            return empty_band_matrix_for(spec)
        df = df.loc[is_positive_label(df[lcol])]
        if df.empty:
            return empty_band_matrix_for(spec)

    if acol not in df.columns:
        return empty_band_matrix_for(spec)

    ct = df.groupby([pcol, acol], dropna=False).size().unstack(fill_value=0)
    ct = ct.reindex(index=list(spec.row_labels), columns=list(spec.col_labels), fill_value=0)
    ct.index.name = spec.matrix_index_name
    return ct.astype(int)


def summarize_ops_pair(queue_df: pd.DataFrame, spec: OpsPairSpec) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if spec.row_grade_col not in queue_df.columns:
        return pd.DataFrame(rows)

    col_default = spec.col_labels[-1]
    for p in spec.row_labels:
        for a in spec.col_labels:
            g = queue_df[
                (queue_df[spec.row_grade_col] == p)
                & (queue_df[spec.col_grade_col] == a)
            ]
            rows.append(
                {
                    "row_band": p,
                    "col_band": a,
                    "cell": cell_label(p, a),
                    "priority": priority_from_pair(p, a, spec),
                    "count": int(len(g)),
                }
            )
    rows.append(
        {
            "row_band": "합계",
            "col_band": "",
            "cell": "",
            "priority": "",
            "count": int(len(queue_df)),
        }
    )
    return pd.DataFrame(rows)


def build_ops_pair_queue(
    row_df: pd.DataFrame,
    col_df: pd.DataFrame | None,
    keys: list[str],
    ops_cfg: dict[str, Any],
    spec: OpsPairSpec,
) -> pd.DataFrame:
    """두 모델 Test 점수 CSV를 join · percentile A~D · 우선순위."""
    a_pct = float(ops_cfg.get("a_top_pct", 1))
    b_pct = float(ops_cfg.get("b_top_pct", 5))
    c_pct = float(ops_cfg.get("c_top_pct", 10))
    col_default = spec.col_labels[-1]

    missing_keys = [k for k in keys if k not in row_df.columns]
    if missing_keys:
        raise KeyError(f"행 모델 점수 파일에 키 컬럼 없음: {missing_keys}")
    if SCORE_COL not in row_df.columns:
        raise KeyError(f"행 모델 점수 파일에 {SCORE_COL} 없음")

    fixed = _pick_existing(row_df, FIXED_SCORE_EXTRA_HEADERS)
    label_cols = _pick_existing(row_df, [PRED_COL, ACTUAL_COL])

    out = row_df[keys + fixed].copy()
    out[spec.row_score_col] = pd.to_numeric(row_df[SCORE_COL], errors="coerce")
    out[spec.row_grade_col] = assign_percentile_bands(
        out[spec.row_score_col],
        a_top_pct=a_pct,
        b_top_pct=b_pct,
        c_top_pct=c_pct,
        prefix=spec.row_prefix,
    )

    out[spec.col_score_col] = np.nan
    out[spec.col_grade_col] = col_default

    if col_df is not None and len(col_df) > 0:
        cb_missing = [k for k in keys if k not in col_df.columns]
        if cb_missing:
            raise KeyError(f"열 모델 점수 파일에 키 컬럼 없음: {cb_missing}")
        if SCORE_COL not in col_df.columns:
            raise KeyError(f"열 모델 점수 파일에 {SCORE_COL} 없음")

        col_part = col_df[keys + [SCORE_COL]].copy()
        col_part = col_part.rename(columns={SCORE_COL: spec.col_score_col})
        col_part[spec.col_score_col] = pd.to_numeric(
            col_part[spec.col_score_col], errors="coerce"
        )
        col_part[spec.col_grade_col] = assign_percentile_bands(
            col_part[spec.col_score_col],
            a_top_pct=a_pct,
            b_top_pct=b_pct,
            c_top_pct=c_pct,
            prefix=spec.col_prefix,
        )
        drop_cols = [c for c in (spec.col_score_col, spec.col_grade_col) if c in out.columns]
        if drop_cols:
            out = out.drop(columns=drop_cols)
        out = out.merge(col_part, on=keys, how="left", validate="one_to_one")
        out[spec.col_grade_col] = out[spec.col_grade_col].fillna(col_default)

    out[CELL_COL] = [
        cell_label(p, a)
        for p, a in zip(out[spec.row_grade_col], out[spec.col_grade_col])
    ]
    out[PRIORITY_COL] = [
        priority_from_pair(p, a, spec)
        for p, a in zip(out[spec.row_grade_col], out[spec.col_grade_col])
    ]
    out[CASE_ID_COL] = spec.case_id

    for c in label_cols:
        if c in row_df.columns:
            out[c] = row_df[c].values

    sort_col = spec.row_score_col
    out = out.sort_values(
        [PRIORITY_COL, sort_col],
        ascending=[True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    ordered = (
        [CASE_ID_COL]
        + keys
        + fixed
        + [
            spec.row_score_col,
            spec.col_score_col,
            spec.row_grade_col,
            spec.col_grade_col,
            CELL_COL,
            PRIORITY_COL,
        ]
        + label_cols
    )
    ordered = [c for c in ordered if c in out.columns]
    return out[ordered]


def _any_positive(series: pd.Series) -> int:
    if series.empty:
        return 0
    return 1 if bool(is_positive_label(series).any()) else 0


def aggregate_entity_queue(
    pk_queue: pd.DataFrame,
    entity_keys: tuple[str, ...],
    ops_cfg: dict[str, Any],
    spec: OpsPairSpec,
) -> pd.DataFrame:
    """PK queue → 엔티티 queue (평균·round(2) percentile · any-positive 라벨)."""
    if pk_queue is None or pk_queue.empty:
        return pd.DataFrame()

    missing = [k for k in entity_keys if k not in pk_queue.columns]
    if missing:
        raise KeyError(f"엔티티 키 없음: {missing}")

    a_pct = float(ops_cfg.get("a_top_pct", 1))
    b_pct = float(ops_cfg.get("b_top_pct", 5))
    c_pct = float(ops_cfg.get("c_top_pct", 10))
    col_default = spec.col_labels[-1]

    work = pk_queue.copy()
    work[spec.row_score_col] = pd.to_numeric(work[spec.row_score_col], errors="coerce")
    work[spec.col_score_col] = pd.to_numeric(work[spec.col_score_col], errors="coerce")

    agg: dict[str, Any] = {
        spec.row_score_col: (spec.row_score_col, "mean"),
        spec.col_score_col: (spec.col_score_col, "mean"),
    }
    for h in FIXED_SCORE_EXTRA_HEADERS:
        if h not in work.columns:
            continue
        if "금액" in h or "AMT" in h.upper():
            work[h] = pd.to_numeric(work[h], errors="coerce")
            agg[h] = (h, "mean")
        else:
            agg[h] = (h, "first")

    if PRED_COL in work.columns:
        agg[PRED_COL] = (PRED_COL, _any_positive)
    if ACTUAL_COL in work.columns:
        agg[ACTUAL_COL] = (ACTUAL_COL, _any_positive)

    grouped = work.groupby(list(entity_keys), dropna=False).agg(**agg).reset_index()

    grouped[spec.row_score_col] = grouped[spec.row_score_col].round(2)
    grouped[spec.col_score_col] = grouped[spec.col_score_col].round(2)

    grouped[spec.row_grade_col] = assign_percentile_bands(
        grouped[spec.row_score_col],
        a_top_pct=a_pct,
        b_top_pct=b_pct,
        c_top_pct=c_pct,
        prefix=spec.row_prefix,
    )
    grouped[spec.col_grade_col] = assign_percentile_bands(
        grouped[spec.col_score_col],
        a_top_pct=a_pct,
        b_top_pct=b_pct,
        c_top_pct=c_pct,
        prefix=spec.col_prefix,
    )
    grouped[spec.col_grade_col] = grouped[spec.col_grade_col].fillna(col_default)

    grouped[CELL_COL] = [
        cell_label(p, a)
        for p, a in zip(grouped[spec.row_grade_col], grouped[spec.col_grade_col])
    ]
    grouped[PRIORITY_COL] = [
        priority_from_pair(p, a, spec)
        for p, a in zip(grouped[spec.row_grade_col], grouped[spec.col_grade_col])
    ]
    grouped[CASE_ID_COL] = spec.case_id

    grouped = grouped.sort_values(
        [PRIORITY_COL, spec.row_score_col],
        ascending=[True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    lead = [CASE_ID_COL] + list(entity_keys)
    tail = [
        c
        for c in grouped.columns
        if c not in lead and c not in (PRED_COL, ACTUAL_COL)
    ]
    labels = [c for c in (PRED_COL, ACTUAL_COL) if c in grouped.columns]
    return grouped[lead + tail + labels]


def positive_in_row_abc_pct(matrix_pos: pd.DataFrame, spec: OpsPairSpec) -> float | None:
    if matrix_pos is None or matrix_pos.empty:
        return None
    total = int(matrix_pos.to_numpy().sum())
    if total <= 0:
        return None
    top_rows = spec.row_labels[:3]
    in_abc = 0
    for r in top_rows:
        if r in matrix_pos.index:
            in_abc += int(matrix_pos.loc[r].sum())
    return round(in_abc / total * 100, 1)


def write_capture_workbook(
    pk_by_case: dict[str, pd.DataFrame],
    entity_by_case: dict[str, pd.DataFrame],
    out_path: Any,
    *,
    unit: str,
) -> None:
    """unit: 'pk' | 'entity' — 케이스별 시트 + 4×4."""
    from pathlib import Path

    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        all_frames = []
        for spec in OPS_PAIR_SPECS:
            q = pk_by_case.get(spec.case_id) if unit == "pk" else entity_by_case.get(spec.case_id)
            if q is None or q.empty:
                continue
            clean = sanitize_for_excel(q)
            all_frames.append(clean)
            prefix = spec.case_id
            clean.to_excel(writer, sheet_name=f"{prefix}_전체"[:31], index=False)
            summarize_ops_pair(clean, spec).to_excel(
                writer, sheet_name=f"{prefix}_요약"[:31], index=False
            )
            summarize_matrix_for(clean, spec).to_excel(
                writer, sheet_name=f"{prefix}_A1"[:31], index=False
            )
            summarize_matrix_for(clean, spec, positive_only=True).to_excel(
                writer, sheet_name=f"{prefix}_A2"[:31], index=False
            )

        if all_frames:
            pd.concat(all_frames, ignore_index=True).to_excel(
                writer, sheet_name="전체", index=False
            )
