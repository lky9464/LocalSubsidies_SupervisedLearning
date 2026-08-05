"""모델 비교 UI용 SHAP·PR curve 로드 (Run 스냅샷 우선)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.evaluate.eval_snapshot import load_per_algo_pr_curve
from src.io.config import resolve_algo_report_dir, resolve_run_algo_report_dir
from src.models.registry import resolve_algo_label


def resolve_shap_total_path(
    cfg: dict[str, Any],
    algo: str,
    *,
    run_id: str | None,
) -> Path | None:
    """Run별 SHAP_total.xlsx 우선, 없으면 repo outputs/reports fallback."""
    run_dir = resolve_run_algo_report_dir(cfg, algo, run_id=run_id)
    if run_dir is not None:
        run_path = run_dir / "SHAP_total.xlsx"
        if run_path.exists():
            return run_path
    shared = resolve_algo_report_dir(cfg, algo) / "SHAP_total.xlsx"
    if shared.exists():
        return shared
    return run_dir / "SHAP_total.xlsx" if run_dir is not None else shared


def load_shap_top10(
    cfg: dict[str, Any],
    algo: str,
    *,
    run_id: str | None,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    path = resolve_shap_total_path(cfg, algo, run_id=run_id)
    if path is None or not path.exists():
        return []

    df = pd.read_excel(path, sheet_name=0)
    share_col = "기여도비중(importance_share)"
    if share_col not in df.columns:
        return []

    work = df.copy()
    work["_abs_share"] = work[share_col].astype(float).abs()
    work = work.sort_values("_abs_share", ascending=False).head(top_n)

    rows: list[dict[str, Any]] = []
    for _, r in work.iterrows():
        share = float(r[share_col])
        direction = str(r.get("기여방향(direction)", "0"))
        rows.append(
            {
                "feature": str(r.get("피처명(feature)", "")),
                "feature_ko": str(r.get("피처명한글(feature_ko)", "")),
                "importance_share": share,
                "direction": direction,
                "direction_label": str(r.get("기여방향표시(direction_label)", "")),
                "signed_share": _signed_share(share, direction),
            }
        )
    return rows


def _signed_share(share: float, direction: str) -> float:
    if direction == "+":
        return share
    if direction == "-":
        return -share
    return 0.0


def build_shap_role_panel(
    cfg: dict[str, Any],
    algo: str | None,
    *,
    run_id: str | None,
    role: str,
    label: str | None,
    top_n: int = 10,
) -> dict[str, Any]:
    if not algo:
        return {
            "role": role,
            "algo": None,
            "label": label,
            "available": False,
            "reason": "해당 역할 모델 없음",
            "top10": [],
        }

    display = label or resolve_algo_label(algo, {})
    top10 = load_shap_top10(cfg, algo, run_id=run_id, top_n=top_n)
    if not top10:
        return {
            "role": role,
            "algo": algo,
            "label": display,
            "available": False,
            "reason": "06 Feature중요도(SHAP) 미실행 또는 SHAP_total.xlsx 없음",
            "top10": [],
        }
    return {
        "role": role,
        "algo": algo,
        "label": display,
        "available": True,
        "reason": "",
        "top10": top10,
    }


def build_pr_curve_role_panel(
    cfg: dict[str, Any],
    algo: str | None,
    *,
    run_id: str | None,
    role: str,
    label: str | None,
) -> dict[str, Any]:
    if not algo:
        return {
            "role": role,
            "algo": None,
            "label": label,
            "available": False,
            "reason": "해당 역할 모델 없음",
            "curve": None,
        }

    display = label or resolve_algo_label(algo, {})
    curve = load_per_algo_pr_curve(cfg, algo, run_id=run_id)
    if not curve or not curve.get("recall"):
        return {
            "role": role,
            "algo": algo,
            "label": display,
            "available": False,
            "reason": "07 평가 미실행 또는 PR curve 데이터 없음",
            "curve": None,
        }
    return {
        "role": role,
        "algo": algo,
        "label": display,
        "available": True,
        "reason": "",
        "curve": curve,
    }


def role_algos_from_ranking(ranking: list[dict]) -> dict[str, str | None]:
    def _pick(role: str) -> str | None:
        for row in ranking:
            if row.get("role") == role:
                algo = str(row.get("algo") or "").strip()
                return algo or None
        return None

    return {
        "primary": _pick("primary"),
        "aux": _pick("aux"),
        "reference": _pick("reference"),
    }


def build_role_insight_panels(
    cfg: dict[str, Any],
    ranking: list[dict],
    *,
    run_id: str | None,
    labels_map: dict[str, str],
    top_n: int = 10,
) -> dict[str, Any]:
    roles = role_algos_from_ranking(ranking)
    panels: dict[str, Any] = {"shap": {}, "pr_curve": {}}

    role_meta = {
        "primary": ("주", "primary"),
        "aux": ("보", "aux"),
        "reference": ("참", "reference"),
    }
    for key, (_ko, role) in role_meta.items():
        algo = roles.get(key)
        label = resolve_algo_label(algo, labels_map) if algo else None
        panels["shap"][key] = build_shap_role_panel(
            cfg, algo, run_id=run_id, role=role, label=label, top_n=top_n
        )
        if key == "reference" and not algo:
            panels["shap"][key]["reason"] = "참조 모델 없음 (2개 모델 학습)"
        panels["pr_curve"][key] = build_pr_curve_role_panel(
            cfg, algo, run_id=run_id, role=role, label=label
        )
        if key == "reference" and not algo:
            panels["pr_curve"][key]["reason"] = "참조 모델 없음 (2개 모델 학습)"

    return panels
