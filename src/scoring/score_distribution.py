"""Test 점수 분포 · TOP10 피처 vs 위험도점수 (PK·엔티티)."""

from __future__ import annotations

import re
from typing import Any, Literal

import numpy as np
import pandas as pd

from src.scoring.ops_capture import parse_entity_keys
from src.scoring.ops_queue import ACTUAL_COL, is_positive_label
from src.scoring.score_table import SCORE_COL

N_SCORE_BINS = 10
TOP_COL_RE = re.compile(r"^기여도TOP(\d{2})_.+\(([^)]+)\)$")

FeatureKind = Literal["numeric", "categorical"]


def score_bin_labels() -> list[str]:
    """07 score_bin_target_rate 와 동일: [0,100) … [900,1000]."""
    labels: list[str] = []
    for i in range(N_SCORE_BINS):
        lo = i * 100
        hi = (i + 1) * 100 if i < N_SCORE_BINS - 1 else 1000
        labels.append(f"{lo}-{hi}")
    return labels


def _bin_mask(scores: pd.Series, i: int) -> pd.Series:
    lo = i * 100
    hi = (i + 1) * 100
    s = pd.to_numeric(scores, errors="coerce")
    if i == N_SCORE_BINS - 1:
        return (s >= lo) & (s <= hi)
    return (s >= lo) & (s < hi)


def aggregate_entity_single_score(
    df: pd.DataFrame,
    entity_keys: tuple[str, ...],
    *,
    score_col: str = SCORE_COL,
    label_col: str = ACTUAL_COL,
    extra_cols: dict[str, str] | None = None,
) -> pd.DataFrame:
    """PK Test 점수 → 엔티티 (평균 round(2) · any-positive 라벨)."""
    if df.empty:
        return pd.DataFrame()

    missing = [k for k in entity_keys if k not in df.columns]
    if missing:
        raise KeyError(f"엔티티 키 없음: {missing}")

    work = df.copy()
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")

    agg: dict[str, Any] = {score_col: (score_col, "mean")}
    if label_col in work.columns:
        agg[label_col] = (label_col, _any_positive_int)

    for col, how in (extra_cols or {}).items():
        if col not in work.columns:
            continue
        if how == "mean":
            work[col] = pd.to_numeric(work[col], errors="coerce")
            agg[col] = (col, "mean")
        elif how == "first":
            agg[col] = (col, "first")
        elif how == "mode":
            agg[col] = (col, _mode_or_first)

    grouped = work.groupby(list(entity_keys), dropna=False).agg(**agg).reset_index()
    grouped[score_col] = grouped[score_col].round(2)
    for col, how in (extra_cols or {}).items():
        if col in grouped.columns and how == "mean":
            grouped[col] = grouped[col].round(2)
    return grouped


def _any_positive_int(series: pd.Series) -> int:
    return 1 if bool(is_positive_label(series).any()) else 0


def _mode_or_first(series: pd.Series) -> str:
    s = series.dropna().astype(str)
    if s.empty:
        return ""
    modes = s.mode()
    return str(modes.iloc[0]) if len(modes) else str(s.iloc[0])


def compute_score_distribution(
    df: pd.DataFrame,
    *,
    score_col: str = SCORE_COL,
    label_col: str = ACTUAL_COL,
) -> dict[str, Any]:
    """10구간 × 전체 건수 + Target 건수."""
    labels = score_bin_labels()
    if df is None or df.empty or score_col not in df.columns:
        return {"bins": [{"label": lb, "total": 0, "target": 0} for lb in labels], "total": 0}

    scores = pd.to_numeric(df[score_col], errors="coerce")
    pos = (
        is_positive_label(df[label_col])
        if label_col in df.columns
        else pd.Series(False, index=df.index)
    )

    bins: list[dict[str, Any]] = []
    for i, lb in enumerate(labels):
        mask = _bin_mask(scores, i)
        total = int(mask.sum())
        target = int((mask & pos).sum()) if total else 0
        bins.append({"label": lb, "total": total, "target": target})

    return {"bins": bins, "total": int(len(df))}


def resolve_feature_kind(feature: str, cfg: dict[str, Any], series: pd.Series) -> FeatureKind:
    cat = set(cfg.get("categorical_candidates") or [])
    if feature in cat:
        return "categorical"
    num = pd.to_numeric(series, errors="coerce")
    valid_ratio = float(num.notna().mean()) if len(series) else 0.0
    if valid_ratio >= 0.85:
        return "numeric"
    nunique = series.dropna().astype(str).nunique()
    if nunique <= 20:
        return "categorical"
    return "numeric"


def find_top_feature_column(columns: list[str], rank: int, feature: str) -> str | None:
    """기여도TOP{rank} 열 — feature 영문명 매칭."""
    want_rank = f"{rank:02d}"
    for c in columns:
        m = TOP_COL_RE.match(c)
        if m and m.group(1) == want_rank and m.group(2) == feature:
            return c
    prefix = f"기여도TOP{rank:02d}_"
    for c in columns:
        if c.startswith(prefix) and c.endswith(f"({feature})"):
            return c
    return None


def _sample_xy(
    x: np.ndarray,
    y: np.ndarray,
    *,
    max_points: int,
) -> list[dict[str, float]]:
    n = len(x)
    if n == 0:
        return []
    idx = np.arange(n)
    if n > max_points:
        rng = np.random.default_rng(42)
        idx = rng.choice(idx, size=max_points, replace=False)
    return [
        {"x": round(float(x[i]), 4), "y": round(float(y[i]), 2)}
        for i in np.sort(idx)
    ]


def _binned_mean_line(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_bins: int = 20,
) -> list[dict[str, float | int]]:
    if len(x) == 0:
        return []
    edges = np.quantile(x, np.linspace(0, 1, n_bins + 1))
    edges = np.unique(edges)
    if len(edges) < 2:
        return [{"x": round(float(np.mean(x)), 4), "y_mean": round(float(np.mean(y)), 2), "n": len(x)}]

    rows: list[dict[str, float | int]] = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        if i == len(edges) - 2:
            mask = (x >= lo) & (x <= hi)
        else:
            mask = (x >= lo) & (x < hi)
        if not mask.any():
            continue
        rows.append(
            {
                "x": round(float(np.mean(x[mask])), 4),
                "y_mean": round(float(np.mean(y[mask])), 2),
                "n": int(mask.sum()),
            }
        )
    return rows


def _linear_regression_line(
    x: np.ndarray,
    y: np.ndarray,
    *,
    n_line: int = 50,
) -> dict[str, Any]:
    if len(x) < 2:
        return {"slope": None, "intercept": None, "points": []}
    coef = np.polyfit(x, y, 1)
    slope, intercept = float(coef[0]), float(coef[1])
    xs = np.linspace(float(x.min()), float(x.max()), n_line)
    points = [
        {"x": round(float(xv), 4), "y": round(float(slope * xv + intercept), 2)}
        for xv in xs
    ]
    return {
        "slope": round(slope, 6),
        "intercept": round(intercept, 4),
        "points": points,
    }


def build_numeric_feature_distribution(
    df: pd.DataFrame,
    *,
    feature_col: str,
    score_col: str = SCORE_COL,
    max_points: int = 8000,
) -> dict[str, Any]:
    work = df[[feature_col, score_col]].copy()
    work[feature_col] = pd.to_numeric(work[feature_col], errors="coerce")
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")
    work = work.dropna()
    if work.empty:
        return {"scatter": [], "binned": [], "regression": {"slope": None, "intercept": None, "points": []}}

    x = work[feature_col].to_numpy(dtype=float)
    y = work[score_col].to_numpy(dtype=float)
    return {
        "scatter": _sample_xy(x, y, max_points=max_points),
        "binned": _binned_mean_line(x, y),
        "regression": _linear_regression_line(x, y),
    }


def build_categorical_feature_distribution(
    df: pd.DataFrame,
    *,
    feature_col: str,
    score_col: str = SCORE_COL,
    max_categories: int = 10,
) -> dict[str, Any]:
    work = df[[feature_col, score_col]].copy()
    work[score_col] = pd.to_numeric(work[score_col], errors="coerce")
    work[feature_col] = work[feature_col].astype(str).str.strip()
    work = work.replace({"": np.nan, "nan": np.nan, "None": np.nan}).dropna(subset=[score_col, feature_col])
    if work.empty:
        return {"bars": [], "other": None}

    grp = (
        work.groupby(feature_col, dropna=False)
        .agg(mean_score=(score_col, "mean"), count=(score_col, "size"))
        .reset_index()
    )
    grp = grp.sort_values("count", ascending=False)
    top = grp.head(max_categories)
    rest = grp.iloc[max_categories:]

    bars = [
        {
            "category": str(r[feature_col]),
            "mean_score": round(float(r["mean_score"]), 2),
            "count": int(r["count"]),
        }
        for _, r in top.iterrows()
    ]
    bars.sort(key=lambda b: b["mean_score"], reverse=True)

    other = None
    if len(rest) > 0:
        other = {
            "category_count": int(len(rest)),
            "total_count": int(rest["count"].sum()),
            "mean_score": round(float(np.average(rest["mean_score"], weights=rest["count"])), 2),
        }

    return {"bars": bars, "other": other}


def build_feature_distribution(
    pk_df: pd.DataFrame,
    cfg: dict[str, Any],
    *,
    feature: str,
    feature_ko: str,
    rank: int,
    unit: Literal["pk", "entity"],
    max_points: int = 8000,
) -> dict[str, Any]:
    col = find_top_feature_column(list(pk_df.columns), rank, feature)
    if col is None:
        return {
            "available": False,
            "reason": f"Test 점수 CSV에 TOP{rank}({feature}) 열 없음 — 06·07 선행",
        }

    entity_keys = parse_entity_keys(cfg)
    if unit == "entity":
        kind = resolve_feature_kind(feature, cfg, pk_df[col])
        extra: dict[str, str] = {col: "mean" if kind == "numeric" else "mode"}
        df = aggregate_entity_single_score(
            pk_df,
            entity_keys,
            extra_cols=extra,
        )
    else:
        df = pk_df

    if col not in df.columns:
        return {"available": False, "reason": "집계 후 피처 열 없음"}

    kind = resolve_feature_kind(feature, cfg, df[col])
    payload: dict[str, Any] = {
        "available": True,
        "feature": feature,
        "feature_ko": feature_ko,
        "rank": rank,
        "unit": unit,
        "kind": kind,
    }
    if kind == "numeric":
        payload["numeric"] = build_numeric_feature_distribution(
            df, feature_col=col, max_points=max_points
        )
    else:
        payload["categorical"] = build_categorical_feature_distribution(df, feature_col=col)
    return payload


def build_score_distribution_payload(
    pk_df: pd.DataFrame,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    entity_keys = parse_entity_keys(cfg)
    ent_df = aggregate_entity_single_score(pk_df, entity_keys)
    return {
        "pk": compute_score_distribution(pk_df),
        "entity": compute_score_distribution(ent_df),
    }
