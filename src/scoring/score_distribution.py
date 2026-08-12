"""Test 점수 분포 (PK·엔티티)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.scoring.ops_capture import parse_entity_keys
from src.scoring.ops_queue import ACTUAL_COL, is_positive_label
from src.scoring.score_table import SCORE_COL

N_SCORE_BINS = 10


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


def _csv_header_columns(path: Path, encoding: str) -> list[str]:
    return list(pd.read_csv(path, encoding=encoding, nrows=0).columns)


def load_test_scores_slim(
    path: Path,
    encoding: str,
    *,
    entity_keys: tuple[str, ...],
    extra_cols: list[str] | None = None,
) -> pd.DataFrame | None:
    """점수 분포용 — 필요 열만 usecols 로드 (전체 CSV dtype=str 금지)."""
    if not path.exists():
        return None
    cols = _csv_header_columns(path, encoding)
    need: list[str] = []
    for c in (SCORE_COL, ACTUAL_COL, *entity_keys, *(extra_cols or [])):
        if c in cols and c not in need:
            need.append(c)
    if SCORE_COL not in need:
        return None
    dtype: dict[str, Any] = {SCORE_COL: "float64"}
    for c in need:
        if c != SCORE_COL:
            dtype[c] = "string"
    return pd.read_csv(
        path,
        encoding=encoding,
        usecols=need,
        dtype=dtype,
        low_memory=False,
    )


def score_distribution_cache_path(csv_path: Path) -> Path:
    return csv_path.with_name(f"{csv_path.stem}_distribution.json")


def read_score_distribution_cache(csv_path: Path) -> dict[str, Any] | None:
    cache = score_distribution_cache_path(csv_path)
    if not cache.exists() or not csv_path.exists():
        return None
    try:
        meta = json.loads(cache.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    st = csv_path.stat()
    if int(meta.get("csv_mtime_ns", -1)) != int(st.st_mtime_ns):
        return None
    if int(meta.get("csv_size", -1)) != int(st.st_size):
        return None
    pk = meta.get("pk")
    entity = meta.get("entity")
    if not isinstance(pk, dict) or not isinstance(entity, dict):
        return None
    return {"pk": pk, "entity": entity}


def write_score_distribution_cache(csv_path: Path, payload: dict[str, Any]) -> None:
    st = csv_path.stat()
    out = {
        "csv_mtime_ns": int(st.st_mtime_ns),
        "csv_size": int(st.st_size),
        "pk": payload.get("pk"),
        "entity": payload.get("entity"),
    }
    cache = score_distribution_cache_path(csv_path)
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")


def get_or_build_score_distribution_payload(
    csv_path: Path,
    cfg: dict[str, Any],
    *,
    encoding: str | None = None,
) -> dict[str, Any] | None:
    """캐시 hit 또는 slim CSV → pk/entity bins. CSV 없으면 None."""
    if not csv_path.exists():
        return None
    cached = read_score_distribution_cache(csv_path)
    if cached is not None:
        return cached
    enc = encoding or str(cfg.get("encoding") or "EUC-KR")
    entity_keys = parse_entity_keys(cfg)
    df = load_test_scores_slim(csv_path, enc, entity_keys=entity_keys)
    if df is None or df.empty:
        return None
    payload = build_score_distribution_payload(df, cfg)
    try:
        write_score_distribution_cache(csv_path, payload)
    except OSError:
        pass
    return payload
