"""평가 결과 기반 모델 순위 · 주·보 역할 (08).

정렬: 상위1% 리프트(Δ≥3%면 단독) → PR-AUC(근접 시) · F1·ROC-AUC 미사용.
primary 자격: PR-AUC 풀 내 하한 가드. 애매 시 4×4로 주·보 확정 권장.
"""

from __future__ import annotations

import json
from functools import cmp_to_key
from pathlib import Path
from typing import Any


def ranking_config(cfg: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "lift_tie_relative_pct": 3.0,
        "pr_auc_tie_absolute": 0.005,
        "primary_pr_auc_abs_gap": 0.01,
        "primary_pr_auc_rel_gap_pct": 3.0,
    }
    if cfg:
        base.update(dict(cfg.get("ranking") or {}))
    return base


def _metric(m: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        if k in m and m[k] is not None:
            try:
                return float(m[k])
            except (TypeError, ValueError):
                continue
    return None


def _lift_from_summary(metrics: dict, lift: dict, algo: str) -> float | None:
    lf = lift.get(algo, {}) or {}
    top1 = _metric(lf, "상위1%리프트(top_1pct_lift)", "top_1pct_lift")
    if top1 is not None:
        return top1
    for k, v in lf.items():
        ks = str(k)
        if ("1%" in ks or "1pct" in ks.lower()) and (
            "리프트" in ks or "lift" in ks.lower()
        ):
            try:
                return float(v)
            except (TypeError, ValueError):
                pass
    return None


def _row_metrics(eval_summary: dict[str, Any], algo: str) -> dict[str, Any]:
    metrics = eval_summary.get("metrics", {}) or {}
    lift = eval_summary.get("lift", {}) or {}
    m = metrics.get(algo, {}) or {}
    lf = lift.get(algo, {}) or {}
    pr = _metric(m, "PR_AUC(AveragePrecision)", "PR_AUC(PR_AUC)", "PR_AUC", "pr_auc")
    roc = _metric(m, "ROC_AUC(ROC_AUC)", "ROC_AUC", "roc_auc")
    f1 = _metric(m, "F1점수(F1)", "F1", "f1")
    top1 = _lift_from_summary(metrics, lift, algo)
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
    return {
        "algo": algo,
        "pr_auc": pr,
        "roc_auc": roc,
        "top1_lift": top1,
        "top1_precision": top1_prec,
        "top1_recall": top1_rec,
        "top5_lift": top5,
        "top5_precision": top5_prec,
        "top5_recall": top5_rec,
        "f1": f1,
    }


def _compare_rows(a: dict[str, Any], b: dict[str, Any], rc: dict[str, Any]) -> int:
    """Return 1 if a>b, -1 if a<b, 0 if tied (both lift and PR-AUC 근접)."""
    lift_a = a.get("top1_lift")
    lift_b = b.get("top1_lift")
    pr_a = a.get("pr_auc")
    pr_b = b.get("pr_auc")

    lift_tie_pct = float(rc.get("lift_tie_relative_pct", 3.0)) / 100.0
    pr_tie_abs = float(rc.get("pr_auc_tie_absolute", 0.005))

    # Missing lift → sort to bottom
    if lift_a is None and lift_b is None:
        pass_lift = True
    elif lift_a is None:
        return -1
    elif lift_b is None:
        return 1
    else:
        denom = max(lift_b, 1e-6)
        delta_lift = abs(lift_a - lift_b) / denom
        if delta_lift >= lift_tie_pct:
            if lift_a > lift_b:
                return 1
            if lift_a < lift_b:
                return -1
        pass_lift = delta_lift < lift_tie_pct

    # Lift 근접 → PR-AUC
    if pr_a is None and pr_b is None:
        return 0 if pass_lift else 0
    if pr_a is None:
        return -1
    if pr_b is None:
        return 1
    delta_pr = abs(pr_a - pr_b)
    if delta_pr >= pr_tie_abs:
        if pr_a > pr_b:
            return 1
        if pr_a < pr_b:
            return -1
    return 0


def _primary_pr_auc_floor(pr_max: float, rc: dict[str, Any]) -> float:
    abs_gap = float(rc.get("primary_pr_auc_abs_gap", 0.01))
    rel_pct = float(rc.get("primary_pr_auc_rel_gap_pct", 3.0)) / 100.0
    gap = max(abs_gap, pr_max * rel_pct if pr_max > 0 else abs_gap)
    return pr_max - gap


def _passes_primary_guard(row: dict[str, Any], pr_max: float | None, rc: dict[str, Any]) -> bool:
    pr = row.get("pr_auc")
    if pr is None:
        return False
    if pr_max is None:
        return True
    return pr >= _primary_pr_auc_floor(pr_max, rc)


def _assign_ranks(sorted_rows: list[dict[str, Any]], rc: dict[str, Any]) -> None:
    n = len(sorted_rows)
    i = 0
    rank_num = 1
    while i < n:
        j = i + 1
        while j < n and _compare_rows(sorted_rows[i], sorted_rows[j], rc) == 0:
            j += 1
        for k in range(i, j):
            sorted_rows[k]["rank"] = rank_num
        rank_num = j + 1
        i = j


def _assign_roles(
    sorted_rows: list[dict[str, Any]], rc: dict[str, Any]
) -> tuple[str | None, str | None, bool]:
    pr_values = [r["pr_auc"] for r in sorted_rows if r.get("pr_auc") is not None]
    pr_max = max(pr_values) if pr_values else None

    primary_algo: str | None = None
    guard_override = False
    for row in sorted_rows:
        if _passes_primary_guard(row, pr_max, rc):
            primary_algo = row["algo"]
            if sorted_rows and row["algo"] != sorted_rows[0]["algo"]:
                guard_override = True
            break

    guard_failed = primary_algo is None
    if guard_failed and sorted_rows:
        # 후보 전원 가드 미통과 — 정렬 1위를 primary 초안(4×4 확정 권장)
        primary_algo = sorted_rows[0]["algo"]
        guard_override = True

    aux_algo: str | None = None
    for row in sorted_rows:
        if row["algo"] != primary_algo:
            aux_algo = row["algo"]
            break

    for idx, row in enumerate(sorted_rows):
        algo = row["algo"]
        if algo == primary_algo:
            row["role"] = "primary"
        elif algo == aux_algo:
            row["role"] = "aux"
        elif idx == 2:
            row["role"] = "reference"
        else:
            row["role"] = "excluded"

    return primary_algo, aux_algo, guard_failed or guard_override


def _ranking_confidence(
    sorted_rows: list[dict[str, Any]],
    rc: dict[str, Any],
    *,
    guard_override: bool,
) -> tuple[str, str]:
    if len(sorted_rows) < 2:
        return "high", "후보 1종 — 자동 순위."

    if _compare_rows(sorted_rows[0], sorted_rows[1], rc) == 0:
        return (
            "low",
            "1·2위 리프트·PR-AUC 모두 근접 — Test 4×4(주A·우선1~4)로 주·보 확정 권장.",
        )

    if guard_override:
        return (
            "low",
            "primary PR-AUC 가드 또는 후보 부족으로 역할 재배치 — "
            "Test 4×4로 주·보 확정 권장.",
        )

    return (
        "high",
        "상위1% 리프트(Δ≥3%) 또는 PR-AUC tie-break로 1·2위 구분 — "
        "4×4 확인 후 ops_queue 반영.",
    )


def build_model_ranking(
    eval_summary: dict[str, Any],
    *,
    algorithms: list[str] | None = None,
    cfg: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """
    Returns (ranking rows, meta with ranking_confidence / ranking_note).
    """
    rc = ranking_config(cfg)
    algos = algorithms or list((eval_summary.get("metrics") or {}).keys())
    rows = [_row_metrics(eval_summary, algo) for algo in algos]

    sorted_rows = sorted(
        rows,
        key=cmp_to_key(lambda a, b: _compare_rows(a, b, rc)),
        reverse=True,
    )
    _assign_ranks(sorted_rows, rc)
    _, _, guard_override = _assign_roles(sorted_rows, rc)
    confidence, note = _ranking_confidence(
        sorted_rows, rc, guard_override=guard_override
    )

    meta = {
        "ranking_confidence": confidence,
        "ranking_note": note,
        "ranking_policy": "top1_lift_then_pr_auc",
    }
    return sorted_rows, meta


def save_model_ranking(
    ranking: list[dict[str, Any]],
    path: Path,
    *,
    meta: dict[str, Any] | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"ranking": ranking}
    if meta:
        payload.update(meta)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def load_ranking_artifact(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.exists():
        return [], {}
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload, {}
    ranking = list(payload.get("ranking", payload))
    meta = {
        k: payload[k]
        for k in ("ranking_confidence", "ranking_note", "ranking_policy")
        if k in payload
    }
    return ranking, meta


def load_model_ranking(path: Path) -> list[dict[str, Any]]:
    ranking, _ = load_ranking_artifact(path)
    return ranking
