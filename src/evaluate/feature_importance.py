"""알고리즘별 Feature 중요도(TOP-N) 산출 — 집계만."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance


def load_column_comments(layout_path: Path) -> dict[str, str]:
    """TLS4902R_Layout.csv 에서 컬럼명→한글 Comment 맵."""
    df = pd.read_csv(layout_path, encoding="utf-8")
    # 일부 환경 EUC-KR일 수 있음
    if "컬럼명" not in df.columns:
        df = pd.read_csv(layout_path, encoding="EUC-KR")
    name_col = "컬럼명" if "컬럼명" in df.columns else df.columns[1]
    comment_col = "Comment" if "Comment" in df.columns else df.columns[2]
    out: dict[str, str] = {}
    for _, row in df.iterrows():
        key = str(row[name_col]).strip()
        val = str(row[comment_col]).strip()
        if key and key != "nan":
            out[key] = val
    return out


def strip_transformer_prefix(name: str) -> str:
    """num__COL / cat__COL → COL"""
    if "__" in name:
        return name.split("__", 1)[1]
    return name


def normalize_importance(values: np.ndarray) -> np.ndarray:
    v = np.asarray(values, dtype=float)
    v = np.nan_to_num(v, nan=0.0)
    v = np.clip(v, a_min=0.0, a_max=None)
    s = float(v.sum())
    if s <= 0:
        return np.zeros_like(v)
    return v / s


def reason_for_feature(
    col: str,
    method: str,
    share: float,
    comments: dict[str, str],
) -> str:
    """비전문가용 사유 문구."""
    meaning = comments.get(col, "레이아웃 Comment 없음")
    method_kr = {
        "tree_impurity": (
            "트리 분할 시 불순도(오분류)를 줄이는 데 기여한 상대 비중입니다. "
            "값이 클수록 모델이 예측에 더 자주·강하게 사용한 변수입니다."
        ),
        "catboost_prediction": (
            "CatBoost 예측값 변화에 대한 기여도(PredictionValuesChange)입니다. "
            "값이 클수록 위험도 점수에 미치는 영향이 큽니다."
        ),
        "permutation_roc_auc": (
            "해당 변수 값을 무작위로 섞었을 때 ROC-AUC가 얼마나 떨어지는지로 측정했습니다. "
            "하락이 클수록 그 변수가 중요합니다."
        ),
        "averaged_base_estimators": (
            "앙상블을 구성하는 여러 기본 모델의 중요도를 평균한 값입니다."
        ),
    }.get(method, "모델이 산출한 상대 기여도입니다.")

    return (
        f"변수 의미: {meaning}({col}). "
        f"기여도(정규화 비중)={share:.2%}. "
        f"측정방법: {method_kr}"
    )


def importance_from_tree_model(
    model: Any,
    feature_names: list[str],
) -> tuple[np.ndarray, str] | None:
    if hasattr(model, "feature_importances_"):
        return np.asarray(model.feature_importances_, dtype=float), "tree_impurity"
    return None


def importance_from_catboost(
    model: Any,
    feature_names: list[str],
) -> tuple[np.ndarray, str]:
    # PredictionValuesChange: 해석에 흔히 사용
    raw = model.get_feature_importance(type="PredictionValuesChange")
    return np.asarray(raw, dtype=float), "catboost_prediction"


def importance_from_easy_ensemble(
    model: Any,
    feature_names: list[str],
) -> tuple[np.ndarray, str] | None:
    """EasyEnsemble 내부 estimator들의 feature_importances_ 평균."""
    if not hasattr(model, "estimators_"):
        return None
    acc = None
    n = 0
    for est in model.estimators_:
        # Bagging/AdaBoost 구조에 따라 다름
        inner = est
        if hasattr(est, "estimators_") and len(getattr(est, "estimators_", [])) > 0:
            # AdaBoostClassifier
            if hasattr(est, "feature_importances_"):
                imp = np.asarray(est.feature_importances_, dtype=float)
            else:
                continue
        elif hasattr(inner, "feature_importances_"):
            imp = np.asarray(inner.feature_importances_, dtype=float)
        else:
            continue
        if acc is None:
            acc = np.zeros_like(imp, dtype=float)
        if acc.shape != imp.shape:
            continue
        acc += imp
        n += 1
    if n == 0 or acc is None:
        return None
    return acc / n, "averaged_base_estimators"


def importance_permutation(
    model: Any,
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    feature_names: list[str],
    *,
    n_repeats: int = 2,
    sample_size: int = 8000,
    random_state: int = 42,
) -> tuple[np.ndarray, str]:
    """메모리 절약: Test 일부 샘플로 permutation importance."""
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

    print(
        f"[fi] permutation importance: sample={len(ys):,}, "
        f"repeats={n_repeats}, features={len(feature_names)}"
    )
    result = permutation_importance(
        model,
        Xs,
        ys,
        n_repeats=n_repeats,
        scoring="roc_auc",
        random_state=random_state,
        n_jobs=1,
    )
    return np.asarray(result.importances_mean, dtype=float), "permutation_roc_auc"


def compute_top_features(
    algo: str,
    model: Any,
    feature_names: list[str],
    X: np.ndarray | pd.DataFrame,
    y: np.ndarray,
    comments: dict[str, str],
    *,
    top_n: int = 10,
    permutation_sample_size: int = 8000,
    permutation_repeats: int = 2,
) -> pd.DataFrame:
    """알고리즘별 TOP-N Feature 표 생성."""
    method = ""
    values: np.ndarray | None = None

    def _perm() -> tuple[np.ndarray, str]:
        return importance_permutation(
            model,
            X,
            y,
            feature_names,
            n_repeats=permutation_repeats,
            sample_size=permutation_sample_size,
        )

    from src.models.registry import family_of, normalize_algo_id

    family = family_of(normalize_algo_id(algo))
    if family == "catboost":
        values, method = importance_from_catboost(model, feature_names)
    elif family in ("random_forest", "gradient_boosting"):
        got = importance_from_tree_model(model, feature_names)
        if got is None:
            values, method = _perm()
        else:
            values, method = got
    elif family == "easy_ensemble":
        got = importance_from_easy_ensemble(model, feature_names)
        if got is None:
            values, method = _perm()
        else:
            values, method = got
    elif family == "stacked_ensemble":
        values, method = _perm()
    else:
        got = importance_from_tree_model(model, feature_names)
        if got is None:
            values, method = _perm()
        else:
            values, method = got

    assert values is not None
    if len(values) != len(feature_names):
        # 길이 불일치 시 이름  Truncate/pad
        m = min(len(values), len(feature_names))
        values = values[:m]
        feature_names = feature_names[:m]

    share = normalize_importance(values)
    order = np.argsort(-share)[:top_n]

    rows = []
    for rank, i in enumerate(order, start=1):
        raw_name = feature_names[i]
        col = strip_transformer_prefix(raw_name)
        rows.append(
            {
                "순위(rank)": rank,
                "알고리즘(algorithm)": algo,
                "피처명(feature)": col,
                "피처명한글(feature_ko)": comments.get(col, ""),
                "기여도비중(importance_share)": float(share[i]),
                "기여도원점수(importance_raw)": float(values[i]),
                "측정방법(method)": method,
                "사유(reason)": reason_for_feature(col, method, float(share[i]), comments),
            }
        )
    return pd.DataFrame(rows)
