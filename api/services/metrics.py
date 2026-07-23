"""Metrics / ranking table logic (ported from app.ui.metrics_table)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from api.constants import COMPARE_COLUMNS, DEFAULT_RADAR_METRICS
from src.evaluate.eval_snapshot import load_eval_maps_for_run, pick_eval_for_algo
from src.models.registry import build_algo_labels_map, resolve_algo_label


def load_eval_maps(
    cfg: dict[str, Any],
    *,
    run_id: str | None = None,
    algos: list[str] | None = None,
) -> tuple[dict, dict]:
    return load_eval_maps_for_run(cfg, run_id=run_id, algos=algos)


def _lift_get(lf: dict, *keys: str) -> Any:
    for k in keys:
        if k in lf and lf[k] is not None:
            return lf[k]
    return None


def _topk_recall(lf: dict, pct: int) -> Any:
    direct = _lift_get(
        lf,
        f"상위{pct}%양성포착비율(top_{pct}pct_recall)",
        f"top_{pct}pct_recall",
    )
    if direct is not None:
        return direct
    rate = _lift_get(
        lf,
        f"상위{pct}%양성비율(top_{pct}pct_positive_rate)",
        f"top_{pct}pct_positive_rate",
    )
    base = _lift_get(lf, "전체양성비율(base_positive_rate)", "base_positive_rate")
    k = _lift_get(lf, f"상위{pct}%건수(top_{pct}pct_count)", f"top_{pct}pct_count")
    if rate is not None and base is not None and k is not None:
        try:
            rate_f, base_f, k_f = float(rate), float(base), float(k)
            if base_f > 0 and k_f > 0:
                n_est = k_f / (float(pct) / 100.0)
                return (rate_f * k_f) / (base_f * n_est)
        except (TypeError, ValueError):
            pass
    lift = _lift_get(lf, f"상위{pct}%리프트(top_{pct}pct_lift)", f"top_{pct}pct_lift")
    if lift is not None:
        try:
            return float(lift) * (float(pct) / 100.0)
        except (TypeError, ValueError):
            pass
    return None


def _coalesce(*vals: Any) -> Any:
    for v in vals:
        if v is not None:
            return v
    return None


def _row_from_parts(
    rank: Any,
    algo: str,
    role: Any,
    ranking_row: dict,
    m: dict,
    lf: dict,
    labels_map: dict[str, str],
) -> dict:
    return {
        "순위": rank,
        "알고리즘": resolve_algo_label(algo, labels_map),
        "algo_key": algo,
        "역할": role,
        "PR-AUC": _coalesce(
            ranking_row.get("pr_auc"), m.get("PR_AUC(AveragePrecision)")
        ),
        "ROC-AUC": _coalesce(ranking_row.get("roc_auc"), m.get("ROC_AUC(ROC_AUC)")),
        "F1": _coalesce(ranking_row.get("f1"), m.get("F1점수(F1)")),
        "상위1%리프트": _coalesce(
            ranking_row.get("top1_lift"),
            _lift_get(lf, "상위1%리프트(top_1pct_lift)", "top_1pct_lift"),
        ),
        "상위1%양성비중": _coalesce(
            ranking_row.get("top1_precision"),
            _lift_get(
                lf, "상위1%양성비율(top_1pct_positive_rate)", "top_1pct_positive_rate"
            ),
        ),
        "상위1%양성포착": _coalesce(
            ranking_row.get("top1_recall"), _topk_recall(lf, 1)
        ),
        "상위5%리프트": _coalesce(
            ranking_row.get("top5_lift"),
            _lift_get(lf, "상위5%리프트(top_5pct_lift)", "top_5pct_lift"),
        ),
        "상위5%양성비중": _coalesce(
            ranking_row.get("top5_precision"),
            _lift_get(
                lf, "상위5%양성비율(top_5pct_positive_rate)", "top_5pct_positive_rate"
            ),
        ),
        "상위5%양성포착": _coalesce(
            ranking_row.get("top5_recall"), _topk_recall(lf, 5)
        ),
    }


def build_compare_frame(
    cfg: dict[str, Any],
    ranking: list[dict],
    *,
    allow_global_fallback: bool = True,
    run_id: str | None = None,
) -> pd.DataFrame:
    algos = [r["algo"] for r in ranking] if ranking else []
    lift_map, metrics_map = load_eval_maps(cfg, run_id=run_id, algos=algos)
    labels_map = build_algo_labels_map(cfg)
    rows: list[dict] = []

    if ranking:
        for r in ranking:
            algo = r["algo"]
            m, lf = pick_eval_for_algo(lift_map, metrics_map, algo)
            rows.append(
                _row_from_parts(
                    r.get("rank"), algo, r.get("role"), r, m, lf, labels_map
                )
            )
    elif allow_global_fallback and metrics_map:
        for i, algo in enumerate(metrics_map.keys(), start=1):
            m, lf = pick_eval_for_algo(lift_map, metrics_map, algo)
            rows.append(_row_from_parts(i, algo, None, {}, m, lf, labels_map))

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in COMPARE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[COMPARE_COLUMNS + (["algo_key"] if "algo_key" in df.columns else [])]
    if "순위" in df.columns:
        df = df.sort_values("순위", ascending=True, na_position="last")
    return df.reset_index(drop=True)


def sort_ops_summary_priority(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    out = summary.copy()
    if "priority" in out.columns:
        out = out.sort_values(
            ["priority"]
            + [c for c in ("primary_band", "aux_band") if c in out.columns],
            kind="mergesort",
        )
        return out.reset_index(drop=True)
    if "grade" in out.columns:
        order = {"S": 0, "A": 1, "B": 2, "C": 3}
        out["_ord"] = out["grade"].map(lambda g: order.get(str(g), 99))
        out = out.sort_values("_ord").drop(columns=["_ord"])
        return out.reset_index(drop=True)
    return out


def format_ops_summary(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    rename = {
        "primary_band": "주등급",
        "aux_band": "보등급",
        "cell": "조합",
        "priority": "우선순위",
        "cnt": "건수",
        "grade": "주등급",
        "cross_check": "조합",
    }
    return summary.rename(columns={k: v for k, v in rename.items() if k in summary.columns})


def _parse_metric_value(v: Any) -> float | None:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def radar_chart_data(compare_df: pd.DataFrame, metrics: list[str] | None = None) -> dict:
    """Min-max normalized radar series for Recharts (모델별 algo_key 고유)."""
    if compare_df.empty:
        return {"metrics": [], "series": []}

    numeric_cols = [
        "PR-AUC",
        "ROC-AUC",
        "F1",
        "상위1%리프트",
        "상위1%양성비중",
        "상위1%양성포착",
        "상위5%리프트",
        "상위5%양성비중",
        "상위5%양성포착",
    ]
    available = [c for c in numeric_cols if c in compare_df.columns]
    selected = metrics or list(DEFAULT_RADAR_METRICS)
    selected = [m for m in selected if m in available]
    if len(selected) < 3:
        return {"metrics": selected, "series": []}

    mins = {m: float("inf") for m in selected}
    maxs = {m: float("-inf") for m in selected}
    for _, row in compare_df.iterrows():
        for m in selected:
            fv = _parse_metric_value(row.get(m))
            if fv is None:
                continue
            mins[m] = min(mins[m], fv)
            maxs[m] = max(maxs[m], fv)

    for m in selected:
        if mins[m] == float("inf") or maxs[m] == float("-inf"):
            mins[m] = 0.0
            maxs[m] = 1.0

    series = []
    seen_ids: set[str] = set()
    for idx, row in compare_df.iterrows():
        display = str(row.get("알고리즘") or "")
        algo_key = str(row.get("algo_key") or display or f"model_{idx}")
        series_id = algo_key
        if series_id in seen_ids:
            series_id = f"{algo_key}__{idx}"
        seen_ids.add(series_id)
        values: dict[str, float] = {}
        for m in selected:
            fv = _parse_metric_value(row.get(m))
            if fv is None:
                # 결측은 축 최솟값(0) — 다른 모델과 겹치지 않도록 id는 algo_key 유지
                values[m] = 0.0
                continue
            lo, hi = mins[m], maxs[m]
            if hi > lo:
                values[m] = (fv - lo) / (hi - lo)
            else:
                values[m] = 0.5
        series.append({"id": series_id, "name": display or algo_key, "values": values})

    return {"metrics": selected, "series": series}
