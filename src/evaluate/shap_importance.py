"""알고리즘별 전역 SHAP Feature 중요도(기여비중·방향) — 집계만."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.evaluate.feature_importance import (
    load_column_comments,
    normalize_importance,
    strip_transformer_prefix,
)
from src.models.registry import family_of, normalize_algo_id

_DIRECTION_EPS = 1e-9


def _require_shap():
    try:
        import shap  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "SHAP 산출에 shap 패키지가 필요합니다. pip install -r requirements.txt"
        ) from exc


def _sample_xy(
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    *,
    sample_size: int,
    random_state: int,
) -> tuple[np.ndarray | pd.DataFrame, np.ndarray]:
    n = len(y)
    rng = np.random.RandomState(random_state)
    if n > sample_size:
        idx = rng.choice(n, size=sample_size, replace=False)
        if isinstance(X, pd.DataFrame):
            Xs = X.iloc[idx]
        else:
            Xs = X[idx]
        ys = y[idx]
    else:
        Xs, ys = X, y
    return Xs, ys


def _positive_class_shap_matrix(raw: Any) -> np.ndarray:
    """TreeExplainer / Explainer 출력 → (n_samples, n_features) 양성 클래스 SHAP."""
    if hasattr(raw, "values"):
        raw = raw.values
    if isinstance(raw, list):
        if len(raw) == 1:
            arr = np.asarray(raw[0], dtype=float)
        else:
            arr = np.asarray(raw[1], dtype=float)
    else:
        arr = np.asarray(raw, dtype=float)
    if arr.ndim == 3:
        # (n_samples, n_features, n_outputs)
        arr = arr[:, :, 1 if arr.shape[2] > 1 else 0]
    if arr.ndim != 2:
        raise ValueError(f"SHAP 배열 형상을 해석할 수 없습니다: {arr.shape}")
    return arr


def _tree_shap_values(model: Any, X: np.ndarray | pd.DataFrame) -> np.ndarray:
    import shap

    explainer = shap.TreeExplainer(model)
    return _positive_class_shap_matrix(explainer.shap_values(X))


def _predict_proba_shap_values(
    model: Any,
    X: np.ndarray | pd.DataFrame,
    *,
    background_size: int = 100,
    random_state: int = 42,
) -> np.ndarray:
    """TreeExplainer 불가 모델용 — 소량 배경 Permutation Explainer."""
    import shap

    n_bg = min(background_size, len(X))
    rng = np.random.RandomState(random_state)
    bg_idx = rng.choice(len(X), size=n_bg, replace=False)
    if isinstance(X, pd.DataFrame):
        background = X.iloc[bg_idx]
        eval_x = X
    else:
        background = X[bg_idx]
        eval_x = X

    def _predict_positive(x: np.ndarray) -> np.ndarray:
        proba = model.predict_proba(x)
        proba = np.asarray(proba, dtype=float)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return proba[:, 1]
        return proba.reshape(-1)

    masker = shap.maskers.Independent(background)
    explainer = shap.Explainer(_predict_positive, masker)
    return _positive_class_shap_matrix(explainer(eval_x))


def _shap_from_tree_or_fallback(
    model: Any,
    X: np.ndarray | pd.DataFrame,
    *,
    random_state: int,
) -> tuple[np.ndarray, str]:
    try:
        return _tree_shap_values(model, X), "shap_tree_explainer"
    except Exception:
        return (
            _predict_proba_shap_values(model, X, random_state=random_state),
            "shap_permutation_explainer",
        )


def _shap_easy_ensemble(
    model: Any,
    X: np.ndarray | pd.DataFrame,
    *,
    random_state: int,
) -> tuple[np.ndarray, str]:
    if not hasattr(model, "estimators_"):
        return _shap_from_tree_or_fallback(model, X, random_state=random_state)

    parts: list[np.ndarray] = []
    for est in model.estimators_:
        inner = est
        if hasattr(est, "estimators_") and len(getattr(est, "estimators_", [])) > 0:
            tree_svs: list[np.ndarray] = []
            for tree in est.estimators_:
                try:
                    tree_svs.append(_tree_shap_values(tree, X))
                except Exception:
                    continue
            if tree_svs:
                parts.append(np.mean(tree_svs, axis=0))
                continue
        try:
            parts.append(_tree_shap_values(inner, X))
        except Exception:
            continue

    if not parts:
        return _shap_from_tree_or_fallback(model, X, random_state=random_state)
    return np.mean(parts, axis=0), "shap_easy_ensemble_average"


def _shap_stacked_ensemble(
    model: Any,
    X: np.ndarray | pd.DataFrame,
    *,
    random_state: int,
) -> tuple[np.ndarray, str]:
    parts: list[np.ndarray] = []
    named = getattr(model, "named_estimators_", None)
    if named:
        for _name, est in named.items():
            try:
                parts.append(_tree_shap_values(est, X))
            except Exception:
                continue
    elif hasattr(model, "estimators_"):
        for est in model.estimators_:
            try:
                parts.append(_tree_shap_values(est, X))
            except Exception:
                continue

    if parts:
        return np.mean(parts, axis=0), "shap_stacked_base_average"
    return _predict_proba_shap_values(model, X, random_state=random_state), "shap_permutation_explainer"


def compute_global_shap_values(
    algo: str,
    model: Any,
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    *,
    sample_size: int = 8000,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray, str, int]:
    """
    Test 표본 SHAP 집계.

    Returns
    -------
    mean_abs, mean_signed, method, n_samples
    """
    _require_shap()
    Xs, ys = _sample_xy(X, y, sample_size=sample_size, random_state=random_state)
    n_samples = len(ys)
    family = family_of(normalize_algo_id(algo))

    print(
        f"[shap] {algo}: sample={n_samples:,}, features="
        f"{Xs.shape[1] if hasattr(Xs, 'shape') else '?'}"
    )

    if family == "catboost":
        shap_matrix, method = _shap_from_tree_or_fallback(model, Xs, random_state=random_state)
    elif family == "easy_ensemble":
        shap_matrix, method = _shap_easy_ensemble(model, Xs, random_state=random_state)
    elif family == "stacked_ensemble":
        shap_matrix, method = _shap_stacked_ensemble(model, Xs, random_state=random_state)
    else:
        shap_matrix, method = _shap_from_tree_or_fallback(model, Xs, random_state=random_state)

    mean_signed = np.asarray(shap_matrix, dtype=float).mean(axis=0)
    mean_abs = np.abs(mean_signed)
    return mean_abs, mean_signed, method, n_samples


def _direction_for_value(value: float) -> tuple[str, str]:
    if value > _DIRECTION_EPS:
        return "+", "양(+)"
    if value < -_DIRECTION_EPS:
        return "-", "음(-)"
    return "0", "중립(0)"


def _reason_for_shap_feature(
    col: str,
    share: float,
    direction_label: str,
    comments: dict[str, str],
) -> str:
    meaning = comments.get(col, "레이아웃 Comment 없음")
    direction_kr = {
        "양(+)": "값이 클수록 위험도(양성 확률)를 높이는 경향이 있습니다.",
        "음(-)": "값이 클수록 위험도(양성 확률)를 낮추는 경향이 있습니다.",
        "중립(0)": "Test 표본에서 평균 기여 방향이 뚜렷하지 않습니다.",
    }.get(direction_label, "")
    return (
        f"변수 의미: {meaning}({col}). "
        f"기여비중={share:.2%}. "
        f"기여방향: {direction_label}. {direction_kr} "
        f"측정방법: Test 표본 SHAP 값의 평균(부호) 및 절대값 평균입니다."
    )


def build_shap_total_dataframe(
    algo: str,
    feature_names: list[str],
    mean_abs: np.ndarray,
    mean_signed: np.ndarray,
    comments: dict[str, str],
    *,
    method: str,
    n_samples: int,
) -> pd.DataFrame:
    """전체 Feature SHAP 표 (TOP N UI용 — 모든 변수 포함)."""
    if len(mean_abs) != len(feature_names):
        m = min(len(mean_abs), len(feature_names))
        mean_abs = mean_abs[:m]
        mean_signed = mean_signed[:m]
        feature_names = feature_names[:m]

    share = normalize_importance(mean_abs)
    order = np.argsort(-share)

    rows: list[dict[str, Any]] = []
    for rank, i in enumerate(order, start=1):
        col = strip_transformer_prefix(feature_names[i])
        direction, direction_label = _direction_for_value(float(mean_signed[i]))
        share_i = float(share[i])
        rows.append(
            {
                "순위(rank)": rank,
                "알고리즘(algorithm)": algo,
                "피처명(feature)": col,
                "피처명한글(feature_ko)": comments.get(col, ""),
                "기여도비중(importance_share)": share_i,
                "기여도원점수(importance_raw)": float(mean_abs[i]),
                "평균SHAP부호(mean_shap_signed)": float(mean_signed[i]),
                "기여방향(direction)": direction,
                "기여방향표시(direction_label)": direction_label,
                "측정방법(method)": method,
                "표본수(n_samples)": int(n_samples),
                "사유(reason)": _reason_for_shap_feature(
                    col, share_i, direction_label, comments
                ),
            }
        )
    return pd.DataFrame(rows)


def compute_shap_total(
    algo: str,
    model: Any,
    feature_names: list[str],
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    comments: dict[str, str],
    *,
    sample_size: int = 8000,
    random_state: int = 42,
) -> pd.DataFrame:
    """알고리즘별 전체 Feature SHAP 중요도 표."""
    mean_abs, mean_signed, method, n_samples = compute_global_shap_values(
        algo,
        model,
        X,
        y,
        sample_size=sample_size,
        random_state=random_state,
    )
    return build_shap_total_dataframe(
        algo,
        feature_names,
        mean_abs,
        mean_signed,
        comments,
        method=method,
        n_samples=n_samples,
    )


def write_shap_total_xlsx(path: Path, df: pd.DataFrame) -> None:
    """outputs/reports/{algo}/SHAP_total.xlsx 저장."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="전체(all)", index=False)
        pd.DataFrame(
            [
                {
                    "안내": (
                        "기여도비중(importance_share)은 mean |SHAP|를 해당 알고리즘 내 "
                        "합=1로 정규화한 값입니다. "
                        "기여방향(direction)은 Test 표본 SHAP 평균 부호입니다: "
                        "양(+)은 값 증가 시 위험도 상승 경향, 음(-)은 하락 경향을 의미합니다. "
                        "점검 우선순위(위험도 점수)와 별개의 참고 설명 자료입니다. "
                        "행단위 SHAP·raw 데이터는 포함되지 않습니다."
                    )
                }
            ]
        ).to_excel(writer, sheet_name="안내(guide)", index=False)


__all__ = [
    "build_shap_total_dataframe",
    "compute_global_shap_values",
    "compute_shap_total",
    "load_column_comments",
    "write_shap_total_xlsx",
]
