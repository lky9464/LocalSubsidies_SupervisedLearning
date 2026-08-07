"""모델 비교 — 점수 분포 · TOP10 피처 분포 API."""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

from api.services.model_insights import (
    load_shap_top10,
    role_algos_from_ranking,
)
from src.io.config import resolve_algo_score_csv
from src.models.registry import resolve_algo_label
from src.scoring.score_distribution import (
    build_feature_distribution,
    build_score_distribution_payload,
)


def _load_test_scores(cfg: dict[str, Any], algo: str, *, run_id: str | None) -> pd.DataFrame | None:
    path = resolve_algo_score_csv(cfg, algo, "test", run_id=run_id)
    if not path.exists():
        return None
    encoding = cfg.get("encoding", "EUC-KR")
    return pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False)


def _role_panel_unavailable(role: str, algo: str | None, label: str | None, reason: str) -> dict[str, Any]:
    return {
        "role": role,
        "algo": algo,
        "label": label,
        "available": False,
        "reason": reason,
        "pk": None,
        "entity": None,
    }


def build_score_distribution_panels(
    cfg: dict[str, Any],
    ranking: list[dict],
    *,
    run_id: str | None,
    labels_map: dict[str, str],
) -> dict[str, Any]:
    roles = role_algos_from_ranking(ranking)
    out: dict[str, Any] = {}

    role_meta = {
        "primary": ("primary", "주"),
        "aux": ("aux", "보"),
        "reference": ("reference", "참"),
    }
    for key, (role, _ko) in role_meta.items():
        algo = roles.get(key)
        label = resolve_algo_label(algo, labels_map) if algo else None
        if not algo:
            reason = (
                "참조 모델 없음 (2개 모델 학습)"
                if key == "reference"
                else "해당 역할 모델 없음"
            )
            out[key] = _role_panel_unavailable(role, None, label, reason)
            continue

        df = _load_test_scores(cfg, algo, run_id=run_id)
        if df is None or df.empty:
            out[key] = _role_panel_unavailable(
                role,
                algo,
                label,
                "07 평가 미실행 또는 Test 점수 CSV 없음",
            )
            continue

        dist = build_score_distribution_payload(df, cfg)
        out[key] = {
            "role": role,
            "algo": algo,
            "label": label or algo,
            "available": True,
            "reason": "",
            **dist,
        }
    return out


def build_feature_distribution_response(
    cfg: dict[str, Any],
    ranking: list[dict],
    *,
    run_id: str | None,
    role_key: str,
    rank: int,
    unit: Literal["pk", "entity"],
    labels_map: dict[str, str],
    top_n: int = 10,
) -> dict[str, Any]:
    roles = role_algos_from_ranking(ranking)
    algo = roles.get(role_key)
    label = resolve_algo_label(algo, labels_map) if algo else None

    if not algo:
        return {
            "available": False,
            "reason": "해당 역할 모델 없음",
            "role": role_key,
            "algo": None,
            "label": label,
        }

    top10 = load_shap_top10(cfg, algo, run_id=run_id, top_n=top_n)
    if not top10:
        return {
            "available": False,
            "reason": "06 SHAP 미실행 또는 SHAP_total.xlsx 없음",
            "role": role_key,
            "algo": algo,
            "label": label or algo,
        }

    if rank < 1 or rank > len(top10):
        return {
            "available": False,
            "reason": f"rank는 1~{len(top10)} 범위",
            "role": role_key,
            "algo": algo,
            "label": label or algo,
        }

    feat = top10[rank - 1]
    df = _load_test_scores(cfg, algo, run_id=run_id)
    if df is None or df.empty:
        return {
            "available": False,
            "reason": "07 Test 점수 CSV 없음",
            "role": role_key,
            "algo": algo,
            "label": label or algo,
        }

    max_pts = int(cfg.get("feature_importance", {}).get("shap_sample_size", 8000))
    result = build_feature_distribution(
        df,
        cfg,
        feature=str(feat["feature"]),
        feature_ko=str(feat.get("feature_ko") or feat["feature"]),
        rank=rank,
        unit=unit,
        max_points=max_pts,
    )
    return {
        **result,
        "role": role_key,
        "algo": algo,
        "label": label or algo,
        "top10": top10,
    }
