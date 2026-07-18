"""공통 전처리: Train fit → Test transform.

16GB RAM PC 대응:
- sklearn 경로는 One-Hot 대신 OrdinalEncoder 사용 (차원·메모리 폭증 방지)
- 변환 결과는 float32
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder


def build_feature_lists(
    df: pd.DataFrame,
    cfg: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    """사용 피처 / 범주형 / 수치형 목록."""
    exclude = set(cfg.get("exclude_features", []))
    exclude.update(cfg.get("key_columns", []))
    exclude.add(cfg.get("target_column", "TAET_YN"))

    candidates = [c for c in df.columns if c not in exclude]
    cat_cand = set(cfg.get("categorical_candidates", []))
    categorical = [c for c in candidates if c in cat_cand]
    numeric = [c for c in candidates if c not in categorical]
    return candidates, categorical, numeric


def time_split_masks(
    df: pd.DataFrame,
    period_col: str,
    train_start: str,
    train_end: str,
    test_start: str,
    test_end: str,
) -> tuple[pd.Series, pd.Series]:
    """시계열 분할 마스크."""
    p = df[period_col].astype(str).str.replace(r"\D", "", regex=True)
    train = (p >= train_start) & (p <= train_end)
    test = (p >= test_start) & (p <= test_end)
    return train, test


def random_split_masks(
    df: pd.DataFrame,
    *,
    test_size: float = 0.3,
    random_state: int = 42,
) -> tuple[pd.Series, pd.Series]:
    """행 단위 랜덤 Train/Test 마스크 (겹치지 않음)."""
    from sklearn.model_selection import train_test_split

    idx = df.index.to_numpy()
    train_idx, test_idx = train_test_split(
        idx, test_size=float(test_size), random_state=int(random_state), shuffle=True
    )
    train = df.index.isin(train_idx)
    test = df.index.isin(test_idx)
    return pd.Series(train, index=df.index), pd.Series(test, index=df.index)


def _to_numeric_frame(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in cols:
        out[c] = pd.to_numeric(df[c], errors="coerce")
    return out


def fit_preprocessor(
    X_train: pd.DataFrame,
    categorical: list[str],
    numeric: list[str],
    for_catboost: bool = False,
) -> tuple[Any, list[str]]:
    """
    sklearn용 ColumnTransformer 또는 CatBoost용 단순 imputer 정보를 반환.
    for_catboost=True이면 범주는 문자열 유지, 수치만 중앙값 대체 메타를 반환.

    ※ One-Hot 금지: 고카디널리티 × 대행수 시 수십 GB 할당이 발생함.
    """
    if for_catboost:
        num_medians: dict[str, float] = {}
        for c in numeric:
            if c in X_train.columns:
                med = pd.to_numeric(X_train[c], errors="coerce").median()
                num_medians[c] = float(med) if pd.notna(med) else 0.0
            else:
                num_medians[c] = 0.0
        meta = {"type": "catboost", "num_medians": num_medians, "cat_fill": "MISSING"}
        return meta, categorical

    transformers = []
    if numeric:
        transformers.append(
            (
                "num",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                    ]
                ),
                numeric,
            )
        )
    if categorical:
        transformers.append(
            (
                "cat",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="MISSING")),
                        (
                            "ordinal",
                            OrdinalEncoder(
                                handle_unknown="use_encoded_value",
                                unknown_value=-1,
                                dtype=np.float32,
                            ),
                        ),
                    ]
                ),
                categorical,
            )
        )

    # sparse_threshold=0: 이후 단계에서도 밀집 소형 행렬만 유지 (컬럼 수 ≈ 원본 피처 수)
    pre = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        sparse_threshold=0,
        n_jobs=1,
    )

    parts: list[pd.DataFrame] = []
    if numeric:
        parts.append(_to_numeric_frame(X_train, numeric))
    if categorical:
        cat_df = X_train[categorical].astype(str).fillna("MISSING")
        parts.append(cat_df)
    X_fit = pd.concat(parts, axis=1) if parts else X_train.iloc[:, 0:0]

    print(
        f"[preprocess] sklearn OrdinalEncoder fit "
        f"(num={len(numeric)}, cat={len(categorical)}, rows={len(X_fit):,})"
    )
    pre.fit(X_fit)
    return pre, categorical


def transform_features(
    X: pd.DataFrame,
    preprocessor: Any,
    categorical: list[str],
    numeric: list[str],
) -> tuple[np.ndarray | pd.DataFrame, list[str] | None]:
    """전처리 적용. CatBoost 메타면 DataFrame, sklearn이면 float32 ndarray."""
    if isinstance(preprocessor, dict) and preprocessor.get("type") == "catboost":
        out = pd.DataFrame(index=X.index)
        for c in numeric:
            s = pd.to_numeric(X[c], errors="coerce") if c in X.columns else pd.Series(np.nan, index=X.index)
            out[c] = s.fillna(preprocessor["num_medians"].get(c, 0.0))
        for c in categorical:
            if c in X.columns:
                out[c] = X[c].astype(str).fillna(preprocessor["cat_fill"])
            else:
                out[c] = preprocessor["cat_fill"]
        cols = numeric + categorical
        return out[cols], cols

    parts: list[pd.DataFrame] = []
    if numeric:
        parts.append(_to_numeric_frame(X, numeric))
    if categorical:
        parts.append(X[categorical].astype(str).fillna("MISSING") if categorical else pd.DataFrame(index=X.index))
    X_t = pd.concat(parts, axis=1) if parts else X.iloc[:, 0:0]

    arr = preprocessor.transform(X_t)
    if hasattr(arr, "toarray"):
        arr = arr.toarray()
    arr = np.asarray(arr, dtype=np.float32)
    try:
        names = list(preprocessor.get_feature_names_out())
    except Exception:
        names = None
    return arr, names


def encode_target(y: pd.Series, positive_label: str = "Y") -> np.ndarray:
    return (
        y.astype(str)
        .str.strip()
        .str.upper()
        .eq(positive_label.upper())
        .astype(np.int8)
        .to_numpy()
    )
