"""분할 그룹(엔티티) 중복 점검 — 집계만.

행 단위 랜덤 분할에서 같은 사업·기관의 다른 기준년월 행이 Train/Test에 나뉘어
들어가면, 모델이 판별이 아니라 엔티티 암기로 점수를 얻을 수 있다.
여기서는 개별 ID를 출력하지 않고 비율·건수만 산출한다.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# Test 양성 엔티티 중 "Train에서 이미 양성으로 본" 비율 기준
DEFAULT_WARN_RATIO = 0.5
DEFAULT_STRONG_WARN_RATIO = 0.8

# 행 PK(CRTR_YM·PFM_BIZ_ID·INST_ID) 중 하나라도 null이면 학습·감사에 사용하지 않음
DEFAULT_ROW_PK_COLUMNS = ("CRTR_YM", "PFM_BIZ_ID", "INST_ID")


def drop_rows_missing_group_keys(
    df: pd.DataFrame,
    *,
    key_columns: tuple[str, ...] | list[str] = DEFAULT_ROW_PK_COLUMNS,
    reset_index: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """행 PK(CRTR_YM·PFM_BIZ_ID·INST_ID 등) 결측 행 제외 — 어느 한 컬럼이라도 null이면 제거."""
    cols = [c for c in key_columns if c in df.columns]
    n_before = len(df)
    if not cols:
        return df, {
            "n_rows_before": n_before,
            "n_rows_dropped": 0,
            "n_rows_after": n_before,
            "key_columns_checked": [],
        }
    missing = df[cols].isna().any(axis=1)
    n_drop = int(missing.sum())
    if n_drop:
        df = df.loc[~missing]
        if reset_index:
            df = df.reset_index(drop=True)
    return df, {
        "n_rows_before": n_before,
        "n_rows_dropped": n_drop,
        "n_rows_after": int(len(df)),
        "key_columns_checked": cols,
    }


def align_labeled_to_split_masks(
    df: pd.DataFrame,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
    *,
    key_columns: tuple[str, ...] | list[str] = DEFAULT_ROW_PK_COLUMNS,
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, dict[str, Any]]:
    """03 전처리와 동일한 PK 결측 제거 후 split_masks 길이와 labeled를 맞춘다."""
    df, pk_drop = drop_rows_missing_group_keys(df, key_columns=key_columns)
    tr = np.asarray(train_mask, dtype=bool)
    te = np.asarray(test_mask, dtype=bool)
    n = len(df)
    if len(tr) != n or len(te) != n:
        raise ValueError(
            f"split_masks(train={len(tr)}, test={len(te)})와 labeled PK 정렬 후 "
            f"행 수({n:,}, 원본 {pk_drop['n_rows_before']:,})가 일치하지 않습니다. "
            "labeled.csv 변경 없이 03_preprocess부터 재실행하세요."
        )
    return df, tr, te, pk_drop


def entity_codes(df: pd.DataFrame, key: str) -> np.ndarray:
    """`A` 또는 `A+B` 형태의 키를 정수 코드 배열로 변환 (ID 값은 반환하지 않음)."""
    cols = [c.strip() for c in str(key).split("+") if c.strip()]
    if not cols:
        raise ValueError("group key가 비어 있습니다.")
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"그룹 키 컬럼 없음: {missing}")
    s = df[cols[0]].astype(str).str.strip()
    for c in cols[1:]:
        s = s.str.cat(df[c].astype(str).str.strip(), sep="\x1f")
    codes, _ = pd.factorize(s, sort=False)
    return codes.astype(np.int64, copy=False)


def group_overlap_stats(
    df: pd.DataFrame,
    key: str,
    y: np.ndarray,
    train_mask: np.ndarray,
    test_mask: np.ndarray,
) -> dict[str, Any]:
    """엔티티(사업·기관) 단위 Train/Test 중복 집계.

    핵심 지표는 `pos_entity_seen_positive_ratio` — Test 양성 엔티티 중 Train에서
    이미 양성으로 등장한 비율. 1에 가까우면 Test 양성 대부분이 "이미 답을 본"
    엔티티이므로 신규 대상 탐지력이 측정되지 않는다.
    """
    codes = entity_codes(df, key)
    y = np.asarray(y).astype(np.int8, copy=False)
    tr = np.asarray(train_mask).astype(bool, copy=False)
    te = np.asarray(test_mask).astype(bool, copy=False)
    if not (len(codes) == len(y) == len(tr) == len(te)):
        raise ValueError("df·y·mask 길이가 다릅니다.")

    pos = y == 1
    n_entities = int(codes.max()) + 1 if len(codes) else 0
    rows_per_entity = np.bincount(codes, minlength=n_entities)
    pos_per_entity = np.bincount(codes, weights=pos.astype(float), minlength=n_entities)

    ent_train = np.unique(codes[tr])
    ent_test = np.unique(codes[te])
    ent_train_pos = np.unique(codes[tr & pos])
    ent_test_pos = np.unique(codes[te & pos])

    n_rows_train = int(tr.sum())
    n_rows_test = int(te.sum())
    n_split_rows = n_rows_train + n_rows_test
    train_frac = (n_rows_train / n_split_rows) if n_split_rows else 0.0

    def _ratio(num: int, den: int) -> float | None:
        return (num / den) if den else None

    n_test_pos_ent = int(len(ent_test_pos))
    seen_ent = int(np.isin(ent_test_pos, ent_train).sum())
    seen_pos_ent = int(np.isin(ent_test_pos, ent_train_pos).sum())

    # 행 기준 가중: Test 양성 행 중 Train에서 이미 양성이던 엔티티에 속한 비율
    test_pos_rows = int((te & pos).sum())
    seen_pos_rows = int(np.isin(codes[te & pos], ent_train_pos).sum())

    # 라벨 고착성: 양성이 1건 이상인 엔티티의 (양성 행 / 전체 행) 평균
    has_pos = pos_per_entity > 0
    stickiness = (
        float(np.mean(pos_per_entity[has_pos] / rows_per_entity[has_pos]))
        if bool(has_pos.any())
        else None
    )

    # 랜덤 분할이라면 기대되는 중복 비율 (엔티티 행 수 m, Train 비율 p 가정)
    if n_test_pos_ent and 0.0 < train_frac < 1.0:
        m = rows_per_entity[ent_test_pos].astype(float)
        expected_overlap = float(np.mean(1.0 - np.power(1.0 - train_frac, m)))
    else:
        expected_overlap = None

    return {
        "group_key": key,
        "n_rows": int(len(codes)),
        "n_rows_train": n_rows_train,
        "n_rows_test": n_rows_test,
        "n_entities": int(len(np.unique(codes))),
        "n_entities_train": int(len(ent_train)),
        "n_entities_test": int(len(ent_test)),
        "rows_per_entity_mean": float(rows_per_entity[rows_per_entity > 0].mean())
        if n_entities
        else None,
        "rows_per_entity_max": int(rows_per_entity.max()) if n_entities else None,
        "n_pos_rows": int(pos.sum()),
        "n_pos_rows_test": test_pos_rows,
        "n_pos_entities": int(has_pos.sum()),
        "n_pos_entities_train": int(len(ent_train_pos)),
        "n_pos_entities_test": n_test_pos_ent,
        "pos_rows_per_pos_entity": _ratio(int(pos.sum()), int(has_pos.sum())),
        "label_stickiness": stickiness,
        "entity_overlap_ratio": _ratio(int(np.isin(ent_test, ent_train).sum()), int(len(ent_test))),
        "pos_entity_seen_ratio": _ratio(seen_ent, n_test_pos_ent),
        "pos_entity_seen_positive_ratio": _ratio(seen_pos_ent, n_test_pos_ent),
        "pos_row_seen_positive_ratio": _ratio(seen_pos_rows, test_pos_rows),
        "expected_overlap_under_random": expected_overlap,
    }


def group_verdict(
    stats_list: list[dict[str, Any]],
    warn_ratio: float = DEFAULT_WARN_RATIO,
    strong_warn_ratio: float = DEFAULT_STRONG_WARN_RATIO,
) -> tuple[str, float | None]:
    """가장 나쁜(높은) 중복 비율로 판정. (verdict, worst_ratio)"""
    ratios = [
        s.get("pos_entity_seen_positive_ratio")
        for s in stats_list
        if s.get("pos_entity_seen_positive_ratio") is not None
    ]
    if not ratios:
        return "SKIP_그룹키없음_또는_Test양성없음", None
    worst = float(max(ratios))
    if worst >= float(strong_warn_ratio):
        return "WARN_그룹누수_강함_분할방식_재검토", worst
    if worst >= float(warn_ratio):
        return "WARN_그룹누수_의심_시간또는그룹분할_대조권장", worst
    return "PASS_그룹중복_낮음", worst
