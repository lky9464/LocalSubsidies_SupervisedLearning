"""모델 비교 지표 표 (대시보드·비교·Run이력 공용)."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from app.ui.common import ALGO_LABELS
from src.io.config import resolve_data_path

METRIC_HELP = {
    "상위N%리프트": (
        "상위 N% 구간의 실제 양성 비율을 전체 양성 비율로 나눈 값입니다. "
        "예: 리프트 10 → 무작위로 고를 때보다 양성(타겟)이 약 10배 많이 포함됩니다."
    ),
    "상위N%양성비중": (
        "상위 N% 안에 실제 양성(타겟)이 차지하는 비율입니다 "
        "(precision@topN%). 높을수록 우선 점검 구간의 적중률이 좋습니다."
    ),
    "상위N%양성포착": (
        "전체 양성(타겟) 중 상위 N%에 포함된 비율입니다 "
        "(recall@topN%). 높을수록 실제 위험 건을 상위 구간에서 많이 잡아냅니다."
    ),
}

COMPARE_COLUMNS = [
    "순위",
    "알고리즘",
    "역할",
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


def load_eval_maps(cfg: dict[str, Any]) -> tuple[dict, dict]:
    summary_path = resolve_data_path(cfg, "algorithms") / "eval_summary.json"
    if not summary_path.exists():
        return {}, {}
    try:
        with open(summary_path, encoding="utf-8") as f:
            summary = json.load(f)
        return summary.get("lift") or {}, summary.get("metrics") or {}
    except OSError:
        return {}, {}


def _lift_get(lf: dict, *keys: str) -> Any:
    for k in keys:
        if k in lf and lf[k] is not None:
            return lf[k]
    return None


def _topk_recall(lf: dict, pct: int) -> Any:
    """eval_summary에 recall 키가 없으면 lift·양성비율로 추정."""
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


def build_compare_frame(cfg: dict[str, Any], ranking: list[dict]) -> pd.DataFrame:
    lift_map, metrics_map = load_eval_maps(cfg)
    rows: list[dict] = []

    if ranking:
        for r in ranking:
            algo = r["algo"]
            lf = lift_map.get(algo) or {}
            m = metrics_map.get(algo) or {}
            rows.append(_row_from_parts(r.get("rank"), algo, r.get("role"), r, m, lf))
    elif metrics_map:
        for i, algo in enumerate(metrics_map.keys(), start=1):
            lf = lift_map.get(algo) or {}
            m = metrics_map.get(algo) or {}
            rows.append(_row_from_parts(i, algo, None, {}, m, lf))

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in COMPARE_COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[COMPARE_COLUMNS]
    if "순위" in df.columns:
        df = df.sort_values("순위", ascending=True, na_position="last")
    return df.reset_index(drop=True)


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
) -> dict:
    return {
        "순위": rank,
        "알고리즘": ALGO_LABELS.get(algo, algo),
        "역할": role,
        "PR-AUC": _coalesce(
            ranking_row.get("pr_auc"), m.get("PR_AUC(AveragePrecision)")
        ),
        "ROC-AUC": _coalesce(ranking_row.get("roc_auc"), m.get("ROC_AUC(ROC_AUC)")),
        "F1": _coalesce(ranking_row.get("f1"), m.get("F1점수(F1)")),
        "상위1%리프트": _coalesce(
            _lift_get(lf, "상위1%리프트(top_1pct_lift)", "top_1pct_lift"),
            ranking_row.get("top1_lift"),
        ),
        "상위1%양성비중": _coalesce(
            _lift_get(
                lf, "상위1%양성비율(top_1pct_positive_rate)", "top_1pct_positive_rate"
            ),
            ranking_row.get("top1_precision"),
        ),
        "상위1%양성포착": _coalesce(
            _topk_recall(lf, 1), ranking_row.get("top1_recall")
        ),
        "상위5%리프트": _coalesce(
            _lift_get(lf, "상위5%리프트(top_5pct_lift)", "top_5pct_lift"),
            ranking_row.get("top5_lift"),
        ),
        "상위5%양성비중": _coalesce(
            _lift_get(
                lf, "상위5%양성비율(top_5pct_positive_rate)", "top_5pct_positive_rate"
            ),
            ranking_row.get("top5_precision"),
        ),
        "상위5%양성포착": _coalesce(
            _topk_recall(lf, 5), ranking_row.get("top5_recall")
        ),
    }


def sort_ops_summary_priority(summary: pd.DataFrame) -> pd.DataFrame:
    """우선순위(priority) 오름차순. 구 S/A/B/C 요약도 grade 컬럼이면 후순위 정렬."""
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


# 하위 호환
sort_ops_summary_sabc = sort_ops_summary_priority


def format_ops_summary(summary: pd.DataFrame) -> pd.DataFrame:
    """DB 요약 컬럼을 UI 한글 라벨로."""
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
