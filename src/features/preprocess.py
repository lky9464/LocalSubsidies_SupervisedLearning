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
    pool_start: str | None = None,
    pool_end: str | None = None,
    period_col: str = "CRTR_YM",
) -> tuple[pd.Series, pd.Series]:
    """행 단위 랜덤 Train/Test 마스크 (겹치지 않음).

    pool_start~pool_end 가 있으면 해당 기간만 분할하고, 밖의 행은 Train/Test 모두 False.
    """
    from sklearn.model_selection import train_test_split

    if pool_start and pool_end:
        p = df[period_col].astype(str).str.replace(r"\D", "", regex=True)
        pool = ((p >= str(pool_start)) & (p <= str(pool_end))).to_numpy()
        idx = df.index.to_numpy()[pool]
    else:
        idx = df.index.to_numpy()
    if len(idx) < 150:
        raise RuntimeError(
            f"random 분할 풀 행 수 부족: {len(idx)}"
            + (f" ({pool_start}~{pool_end})" if pool_start and pool_end else "")
        )
    train_idx, test_idx = train_test_split(
        idx, test_size=float(test_size), random_state=int(random_state), shuffle=True
    )
    train = df.index.isin(train_idx)
    test = df.index.isin(test_idx)
    return pd.Series(train, index=df.index), pd.Series(test, index=df.index)


def group_random_split_masks(
    df: pd.DataFrame,
    *,
    group_key: str = "PFM_BIZ_ID+INST_ID",
    target_col: str = "TAET_YN",
    positive_label: str = "Y",
    test_size: float = 0.3,
    random_state: int = 42,
    pool_start: str | None = None,
    pool_end: str | None = None,
    period_col: str = "CRTR_YM",
) -> tuple[pd.Series, pd.Series]:
    """엔티티(사업·기관) 단위 랜덤 Train/Test — 동일 group_key 행은 항상 같은 쪽.

    pool_start~pool_end 가 있으면 해당 기간만 분할하고, 밖의 행은 Train/Test 모두 False.
    엔티티 라벨은 해당 키 그룹 행 중 하나라도 양성이면 양성(층화 stratify용).
    """
    import warnings

    from sklearn.model_selection import train_test_split

    from src.features.group_audit import entity_codes

    # group_key 컬럼 존재 여부를 풀 행 수 검사보다 먼저 확인
    _ = entity_codes(df.iloc[:1] if len(df) else df, group_key)

    if pool_start and pool_end:
        p = df[period_col].astype(str).str.replace(r"\D", "", regex=True)
        pool = ((p >= str(pool_start)) & (p <= str(pool_end))).to_numpy()
        pool_idx = df.index.to_numpy()[pool]
    else:
        pool = np.ones(len(df), dtype=bool)
        pool_idx = df.index.to_numpy()
    n_pool = int(pool.sum())
    if n_pool < 150:
        raise RuntimeError(
            f"group_random 분할 풀 행 수 부족: {n_pool}"
            + (f" ({pool_start}~{pool_end})" if pool_start and pool_end else "")
        )

    df_pool = df.loc[pool_idx]
    codes = entity_codes(df_pool, group_key)
    y_pool = encode_target(df_pool[target_col], positive_label)
    unique_codes = np.unique(codes)
    n_entities = len(unique_codes)
    if n_entities < 2:
        raise RuntimeError(f"group_random 엔티티 수 부족: {n_entities} (key={group_key})")

    # 엔티티별 any-positive 라벨
    ent_labels = np.array(
        [int(y_pool[codes == c].max()) for c in unique_codes],
        dtype=np.int8,
    )
    stratify: np.ndarray | None = ent_labels
    n_pos_ent = int(ent_labels.sum())
    n_neg_ent = n_entities - n_pos_ent
    if n_pos_ent < 2 or n_neg_ent < 2:
        stratify = None
        warnings.warn(
            f"group_random: 양성/음성 엔티티 수 부족(pos={n_pos_ent}, neg={n_neg_ent}) — "
            "층화 없이 분할합니다.",
            stacklevel=2,
        )
    else:
        # test 쪽에 클래스별 최소 1엔티티 필요
        min_test_pos = max(1, int(np.ceil(n_pos_ent * float(test_size))))
        min_test_neg = max(1, int(np.ceil(n_neg_ent * float(test_size))))
        if min_test_pos >= n_pos_ent or min_test_neg >= n_neg_ent:
            stratify = None
            warnings.warn(
                "group_random: test_size·엔티티 수로 층화 불가 — 층화 없이 분할합니다.",
                stacklevel=2,
            )

    try:
        train_ent, test_ent = train_test_split(
            unique_codes,
            test_size=float(test_size),
            random_state=int(random_state),
            shuffle=True,
            stratify=stratify,
        )
    except ValueError:
        warnings.warn(
            "group_random: stratify 실패 — 층화 없이 재시도합니다.",
            stacklevel=2,
        )
        train_ent, test_ent = train_test_split(
            unique_codes,
            test_size=float(test_size),
            random_state=int(random_state),
            shuffle=True,
        )

    train_ent_set = set(train_ent.tolist())
    test_ent_set = set(test_ent.tolist())
    if train_ent_set & test_ent_set:
        raise RuntimeError("group_random: Train/Test 엔티티 교집합 발생")

    train_pool = np.isin(codes, list(train_ent_set))
    test_pool = np.isin(codes, list(test_ent_set))
    if bool((train_pool & test_pool).any()):
        raise RuntimeError("group_random: Train/Test 행 교집합 발생")

    train = pd.Series(False, index=df.index)
    test = pd.Series(False, index=df.index)
    train.loc[pool_idx] = train_pool
    test.loc[pool_idx] = test_pool
    return train, test


def _parent_entity_context(
    df: pd.DataFrame,
    parent_mask: np.ndarray | pd.Series,
    *,
    group_key: str,
    target_col: str,
    positive_label: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """부모 마스크 안의 (행 위치, 엔티티 코드, 고유 코드, 엔티티 any-positive 라벨)."""
    from src.features.group_audit import entity_codes

    parent = np.asarray(parent_mask, dtype=bool)
    if parent.shape[0] != len(df):
        raise RuntimeError(f"마스크 길이 불일치: mask={parent.shape[0]} df={len(df)}")
    row_pos = np.flatnonzero(parent)
    if len(row_pos) < 150:
        raise RuntimeError(
            f"튜닝용 Train 행 수 부족: {len(row_pos)}. 03_preprocess 분할을 확인하세요."
        )

    df_parent = df.iloc[row_pos]
    codes = entity_codes(df_parent, group_key)
    y_parent = encode_target(df_parent[target_col], positive_label)
    unique_codes = np.unique(codes)
    if len(unique_codes) < 2:
        raise RuntimeError(
            f"group 분할 엔티티 수 부족: {len(unique_codes)} (key={group_key})"
        )

    n_codes = int(codes.max()) + 1
    pos_per_entity = np.bincount(
        codes, weights=(np.asarray(y_parent) == 1).astype(float), minlength=n_codes
    )
    ent_labels = (pos_per_entity[unique_codes] > 0).astype(np.int8)
    return row_pos, codes, unique_codes, ent_labels


def _entity_masks_to_full(
    n_rows: int,
    row_pos: np.ndarray,
    codes: np.ndarray,
    valid_entities: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """부모 내 엔티티 목록 → df 전체 길이의 fit/valid 마스크."""
    valid_local = np.isin(codes, valid_entities)
    fit_m = np.zeros(n_rows, dtype=bool)
    valid_m = np.zeros(n_rows, dtype=bool)
    fit_m[row_pos[~valid_local]] = True
    valid_m[row_pos[valid_local]] = True
    if bool((fit_m & valid_m).any()):
        raise RuntimeError("group 분할: fit/valid 행 교집합 발생")
    return fit_m, valid_m


def group_fold_masks_within_mask(
    df: pd.DataFrame,
    parent_mask: np.ndarray | pd.Series,
    *,
    group_key: str = "PFM_BIZ_ID+INST_ID",
    target_col: str = "TAET_YN",
    positive_label: str = "Y",
    n_folds: int = 3,
    random_state: int = 42,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """부모 마스크(Train) 안에서 엔티티 단위 K-fold fit/valid 마스크 목록.

    동일 group_key 엔티티의 모든 행은 한 fold에만 valid로 들어간다. 엔티티가
    fit과 valid에 동시에 나타나면 RuntimeError.
    """
    import warnings

    from sklearn.model_selection import KFold, StratifiedKFold

    n_folds = int(n_folds)
    if n_folds < 2:
        raise ValueError(f"n_folds는 2 이상이어야 합니다: {n_folds}")

    row_pos, codes, unique_codes, ent_labels = _parent_entity_context(
        df,
        parent_mask,
        group_key=group_key,
        target_col=target_col,
        positive_label=positive_label,
    )
    if len(unique_codes) < n_folds:
        raise RuntimeError(
            f"엔티티 수({len(unique_codes)})가 n_folds({n_folds})보다 적습니다."
        )

    n_pos_ent = int(ent_labels.sum())
    n_neg_ent = len(unique_codes) - n_pos_ent
    if n_pos_ent >= n_folds and n_neg_ent >= n_folds:
        splitter = StratifiedKFold(
            n_splits=n_folds, shuffle=True, random_state=int(random_state)
        )
        split_iter = splitter.split(unique_codes.reshape(-1, 1), ent_labels)
    else:
        warnings.warn(
            f"group_fold: 양성/음성 엔티티 수 부족(pos={n_pos_ent}, neg={n_neg_ent}) — "
            "층화 없이 분할합니다.",
            stacklevel=2,
        )
        splitter = KFold(n_splits=n_folds, shuffle=True, random_state=int(random_state))
        split_iter = splitter.split(unique_codes.reshape(-1, 1))

    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for _, valid_ent_pos in split_iter:
        folds.append(
            _entity_masks_to_full(
                len(df), row_pos, codes, unique_codes[valid_ent_pos]
            )
        )
    return folds


def group_split_masks_within_mask(
    df: pd.DataFrame,
    parent_mask: np.ndarray | pd.Series,
    *,
    group_key: str = "PFM_BIZ_ID+INST_ID",
    target_col: str = "TAET_YN",
    positive_label: str = "Y",
    valid_size: float = 0.2,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """부모 마스크(Train) 안에서 엔티티 단위 단일 fit/valid 분할."""
    import warnings

    from sklearn.model_selection import train_test_split

    row_pos, codes, unique_codes, ent_labels = _parent_entity_context(
        df,
        parent_mask,
        group_key=group_key,
        target_col=target_col,
        positive_label=positive_label,
    )

    stratify: np.ndarray | None = ent_labels
    n_pos_ent = int(ent_labels.sum())
    n_neg_ent = len(unique_codes) - n_pos_ent
    if n_pos_ent < 2 or n_neg_ent < 2:
        stratify = None
        warnings.warn(
            f"group_split: 양성/음성 엔티티 수 부족(pos={n_pos_ent}, neg={n_neg_ent}) — "
            "층화 없이 분할합니다.",
            stacklevel=2,
        )
    try:
        _, valid_ent = train_test_split(
            unique_codes,
            test_size=float(valid_size),
            random_state=int(random_state),
            shuffle=True,
            stratify=stratify,
        )
    except ValueError:
        warnings.warn("group_split: stratify 실패 — 층화 없이 재시도합니다.", stacklevel=2)
        _, valid_ent = train_test_split(
            unique_codes,
            test_size=float(valid_size),
            random_state=int(random_state),
            shuffle=True,
        )
    return _entity_masks_to_full(len(df), row_pos, codes, valid_ent)


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
