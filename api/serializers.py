"""DataFrame / matrix serialization helpers."""

from __future__ import annotations

from typing import Any

import pandas as pd


def df_to_records(df: pd.DataFrame | None) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[col]):
            out[col] = out[col].astype(str)
    return out.where(pd.notnull(out), None).to_dict(orient="records")


def matrix_to_payload(df: pd.DataFrame) -> dict[str, Any]:
    if df is None or df.empty:
        return {"index": [], "columns": [], "data": []}
    return {
        "index": [str(i) for i in df.index.tolist()],
        "columns": [str(c) for c in df.columns.tolist()],
        "data": df.astype(int).values.tolist(),
    }
