"""평가 결과 기반 모델 순위 (1~5). 하드코딩 역할 대신 지표로 산출."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _metric(m: dict[str, Any], *keys: str) -> float:
    for k in keys:
        if k in m and m[k] is not None:
            try:
                return float(m[k])
            except (TypeError, ValueError):
                continue
    return float("-inf")


def build_model_ranking(
    eval_summary: dict[str, Any],
    *,
    algorithms: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    정렬: PR-AUC ↓ → 상위1% 리프트 ↓ → F1 ↓.
    role: 1위 primary, 2위 aux, 3위 reference, 나머지 excluded
      (단, easy_ensemble은 지표와 무관하게 기본 excluded 후보로 두되
       순위 자체는 지표순 — role만 상위 3개에 부여)
    """
    metrics = eval_summary.get("metrics", {}) or {}
    lift = eval_summary.get("lift", {}) or {}
    algos = algorithms or list(metrics.keys())
    rows: list[dict[str, Any]] = []
    for algo in algos:
        m = metrics.get(algo, {}) or {}
        lf = lift.get(algo, {}) or {}
        pr = _metric(
            m, "PR_AUC(AveragePrecision)", "PR_AUC(PR_AUC)", "PR_AUC", "pr_auc"
        )
        roc = _metric(m, "ROC_AUC(ROC_AUC)", "ROC_AUC", "roc_auc")
        f1 = _metric(m, "F1점수(F1)", "F1", "f1")
        top1 = _metric(lf, "상위1%리프트(top_1pct_lift)", "top_1pct_lift")
        if top1 == float("-inf"):
            for k, v in lf.items():
                ks = str(k)
                if ("1%" in ks or "1pct" in ks.lower()) and (
                    "리프트" in ks or "lift" in ks.lower()
                ):
                    try:
                        top1 = float(v)
                        break
                    except (TypeError, ValueError):
                        pass
        top1_prec = _metric(
            lf,
            "상위1%양성비율(top_1pct_positive_rate)",
            "top_1pct_positive_rate",
        )
        top1_rec = _metric(
            lf, "상위1%양성포착비율(top_1pct_recall)", "top_1pct_recall"
        )
        top5 = _metric(lf, "상위5%리프트(top_5pct_lift)", "top_5pct_lift")
        top5_prec = _metric(
            lf,
            "상위5%양성비율(top_5pct_positive_rate)",
            "top_5pct_positive_rate",
        )
        top5_rec = _metric(
            lf, "상위5%양성포착비율(top_5pct_recall)", "top_5pct_recall"
        )
        rows.append(
            {
                "algo": algo,
                "pr_auc": None if pr == float("-inf") else pr,
                "roc_auc": None if roc == float("-inf") else roc,
                "top1_lift": None if top1 == float("-inf") else top1,
                "top1_precision": None if top1_prec == float("-inf") else top1_prec,
                "top1_recall": None if top1_rec == float("-inf") else top1_rec,
                "top5_lift": None if top5 == float("-inf") else top5,
                "top5_precision": None if top5_prec == float("-inf") else top5_prec,
                "top5_recall": None if top5_rec == float("-inf") else top5_rec,
                "f1": None if f1 == float("-inf") else f1,
            }
        )

    rows.sort(
        key=lambda r: (
            r["pr_auc"] if r["pr_auc"] is not None else float("-inf"),
            r["top1_lift"] if r["top1_lift"] is not None else float("-inf"),
            r["f1"] if r["f1"] is not None else float("-inf"),
        ),
        reverse=True,
    )

    out: list[dict[str, Any]] = []
    for i, r in enumerate(rows, start=1):
        if i == 1:
            role = "primary"
        elif i == 2:
            role = "aux"
        elif i == 3:
            role = "reference"
        else:
            role = "excluded"
        out.append({"rank": i, "role": role, **r})
    return out


def save_model_ranking(
    ranking: list[dict[str, Any]],
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"ranking": ranking}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def load_model_ranking(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    return list(payload.get("ranking", payload))
