"""데이터 품질 집계 (행 단위 값 미출력)."""

from __future__ import annotations

from typing import Any

import pandas as pd


def summarize_quality(
    df: pd.DataFrame,
    target_column: str = "TAET_YN",
    period_column: str = "CRTR_YM",
) -> dict[str, Any]:
    """건수·결측률·타겟비율·기간별 건수만 집계."""
    n = len(df)
    summary: dict[str, Any] = {
        "행수(row_count)": n,
        "컬럼수(column_count)": int(df.shape[1]),
    }

    if target_column in df.columns:
        vc = df[target_column].astype(str).str.strip().str.upper().value_counts(dropna=False)
        summary["타겟분포(target_distribution)"] = {str(k): int(v) for k, v in vc.items()}
        pos = int(vc.get("Y", 0))
        summary["양성비율(positive_rate)"] = pos / n if n else 0.0

    if period_column in df.columns:
        by_period = (
            df.groupby(df[period_column].astype(str), dropna=False)
            .size()
            .sort_index()
        )
        summary["기간별건수(rows_by_period)"] = {str(k): int(v) for k, v in by_period.items()}

    # 결측률 Top 15 (비율만)
    miss = (df.isna().mean().sort_values(ascending=False).head(15) * 100).round(2)
    summary["결측률상위(missing_rate_pct_top15)"] = {str(k): float(v) for k, v in miss.items()}

    return summary


def print_summary(summary: dict[str, Any]) -> None:
    print("[quality] ===== 품질 집계 (raw 행 미포함) =====")
    for k, v in summary.items():
        print(f"[quality] {k}: {v}")
