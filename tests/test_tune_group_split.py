"""튜닝 fit/valid 엔티티 무중복 분할 테스트 (합성 패널, 실데이터 미사용)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.preprocess import (
    group_fold_masks_within_mask,
    group_split_masks_within_mask,
)
from src.models.tune import (
    aggregate_fold_scores,
    audit_tune_folds,
    fold_positions_within_use,
    resolve_tune_folds,
)


def _panel_df(n_entities: int = 120, months: int = 4, pos_every: int = 5) -> pd.DataFrame:
    rows = []
    for i in range(n_entities):
        label = "Y" if i % pos_every == 0 else "N"
        for m in range(1, months + 1):
            rows.append(
                {
                    "CRTR_YM": f"2024{m:02d}",
                    "PFM_BIZ_ID": f"B{i:04d}",
                    "INST_ID": f"I{i % 7}",
                    "TAET_YN": label,
                }
            )
    return pd.DataFrame(rows)


def _train_mask(df: pd.DataFrame, holdout_entities: int = 20) -> np.ndarray:
    """뒤쪽 엔티티를 Test로 빼 둔 Train 마스크 (03 group_random 모사)."""
    held = {f"B{i:04d}" for i in range(holdout_entities)}
    return (~df["PFM_BIZ_ID"].isin(held)).to_numpy()


def _entities(df: pd.DataFrame, mask: np.ndarray) -> set[tuple[str, str]]:
    sub = df.loc[mask]
    return set(zip(sub["PFM_BIZ_ID"], sub["INST_ID"]))


def test_group_folds_have_no_entity_overlap() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    folds = group_fold_masks_within_mask(df, train_m, n_folds=3, random_state=42)

    assert len(folds) == 3
    for fit_m, valid_m in folds:
        assert not bool((fit_m & valid_m).any())
        assert not (_entities(df, fit_m) & _entities(df, valid_m))


def test_group_folds_stay_inside_parent_mask() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    folds = group_fold_masks_within_mask(df, train_m, n_folds=3, random_state=7)

    for fit_m, valid_m in folds:
        assert not bool((fit_m & ~train_m).any())
        assert not bool((valid_m & ~train_m).any())


def test_each_entity_is_validated_exactly_once() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    folds = group_fold_masks_within_mask(df, train_m, n_folds=3, random_state=1)

    seen: list[tuple[str, str]] = []
    for _, valid_m in folds:
        seen.extend(_entities(df, valid_m))
    assert len(seen) == len(set(seen))
    assert set(seen) == _entities(df, train_m)


def test_single_group_split_has_no_entity_overlap() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    fit_m, valid_m = group_split_masks_within_mask(
        df, train_m, valid_size=0.25, random_state=42
    )

    assert not (_entities(df, fit_m) & _entities(df, valid_m))
    assert not bool(((fit_m | valid_m) & ~train_m).any())


def test_audit_reports_zero_overlap_for_group_folds() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    folds = group_fold_masks_within_mask(df, train_m, n_folds=3, random_state=42)
    audit = audit_tune_folds(df, folds, group_key="PFM_BIZ_ID+INST_ID")

    assert len(audit) == 3
    for info in audit:
        assert info["entity_overlap"] == 0
        assert info["valid_pos_entities"] > 0


def test_audit_detects_row_level_split_leak() -> None:
    """행 단위 랜덤 분할은 엔티티 교집합이 생겨야 한다 (기존 nested_random 문제)."""
    df = _panel_df()
    train_m = _train_mask(df)
    idx = np.flatnonzero(train_m)
    rng = np.random.default_rng(0)
    valid_idx = rng.choice(idx, size=len(idx) // 5, replace=False)
    valid_m = np.zeros(len(df), dtype=bool)
    valid_m[valid_idx] = True
    fit_m = train_m & ~valid_m

    audit = audit_tune_folds(df, [(fit_m, valid_m)], group_key="PFM_BIZ_ID+INST_ID")
    assert audit[0]["entity_overlap"] > 0


def test_resolve_tune_folds_group_mode() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    cfg = {
        "tune": {"split_mode": "nested_group_random", "n_folds": 3, "random_state": 42},
        "split": {"group_key": "PFM_BIZ_ID+INST_ID"},
    }
    folds, desc, meta = resolve_tune_folds(df, train_m, cfg)

    assert meta["n_folds"] == 3
    assert meta["group_key"] == "PFM_BIZ_ID+INST_ID"
    assert "nested_group_random" in desc
    for fit_m, valid_m in folds:
        assert not (_entities(df, fit_m) & _entities(df, valid_m))


def test_resolve_tune_folds_row_mode_returns_single_fold() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    cfg = {"tune": {"split_mode": "nested_random", "valid_size": 0.2, "random_state": 42}}
    folds, _, meta = resolve_tune_folds(df, train_m, cfg)

    assert len(folds) == 1
    assert meta["n_folds"] == 1
    assert meta["group_key"] is None


def test_aggregate_fold_scores_means_and_std() -> None:
    scores = [
        {"top1_lift": 10.0, "pr_auc": 0.2, "precision": None},
        {"top1_lift": 20.0, "pr_auc": 0.4, "precision": None},
    ]
    agg = aggregate_fold_scores(scores)

    assert agg["top1_lift"] == 15.0
    assert abs(agg["pr_auc"] - 0.3) < 1e-9
    assert agg["top1_lift_std"] == 5.0
    assert agg["precision"] is None


def test_fold_positions_map_back_to_original_rows() -> None:
    """위치 인덱스로 자른 행이 원본 마스크가 가리키는 행과 같아야 한다."""
    df = _panel_df()
    train_m = _train_mask(df)
    folds = group_fold_masks_within_mask(df, train_m, n_folds=3, random_state=42)
    use_pos, fold_idx = fold_positions_within_use(folds, len(df))

    # 모든 fold의 fit|valid 합집합 = Train 마스크
    np.testing.assert_array_equal(use_pos, np.flatnonzero(train_m))

    sub = df.iloc[use_pos].reset_index(drop=True)
    for (fit_m, valid_m), (fit_pos, valid_pos) in zip(folds, fold_idx):
        assert (fit_pos >= 0).all() and (valid_pos >= 0).all()
        pd.testing.assert_frame_equal(
            sub.iloc[fit_pos].reset_index(drop=True),
            df.loc[fit_m].reset_index(drop=True),
        )
        pd.testing.assert_frame_equal(
            sub.iloc[valid_pos].reset_index(drop=True),
            df.loc[valid_m].reset_index(drop=True),
        )


def test_n_folds_below_two_raises() -> None:
    df = _panel_df()
    train_m = _train_mask(df)
    try:
        group_fold_masks_within_mask(df, train_m, n_folds=1)
    except ValueError:
        pass
    else:
        raise AssertionError("ValueError expected")
