"""group_random_split_masks 단위 테스트 (합성 패널, 실데이터 미사용)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.group_audit import drop_rows_missing_group_keys, group_overlap_stats, align_labeled_to_split_masks
from src.features.preprocess import encode_target, group_random_split_masks


def _panel_df(
    entities: list[tuple[str, str, int, list[str]]],
) -> pd.DataFrame:
    """(biz_id, inst_id, label, months) 목록으로 패널 DataFrame 생성."""
    rows = []
    for biz, inst, y, months in entities:
        for ym in months:
            rows.append(
                {
                    "CRTR_YM": ym,
                    "PFM_BIZ_ID": biz,
                    "INST_ID": inst,
                    "TAET_YN": "Y" if y else "N",
                }
            )
    return pd.DataFrame(rows)


def _overlap_stats(df: pd.DataFrame, train_m: pd.Series, test_m: pd.Series) -> dict:
    y = encode_target(df["TAET_YN"], "Y")
    return group_overlap_stats(
        df,
        "PFM_BIZ_ID+INST_ID",
        y,
        train_m.to_numpy(),
        test_m.to_numpy(),
    )


def test_zero_entity_overlap() -> None:
    """동일 PFM_BIZ_ID+INST_ID 가 Train/Test에 동시에 등장하지 않아야 한다."""
    entities = []
    for i in range(40):
        label = 1 if i < 6 else 0
        months = [f"2024{m:02d}" for m in range(1, 5)]
        entities.append((f"B{i:03d}", f"I{i % 3}", label, months))
    df = _panel_df(entities)

    train_m, test_m = group_random_split_masks(
        df,
        group_key="PFM_BIZ_ID+INST_ID",
        pool_start="202401",
        pool_end="202412",
        test_size=0.3,
        random_state=42,
    )

    assert not bool((train_m & test_m).any())
    stats = _overlap_stats(df, train_m, test_m)
    assert stats["entity_overlap_ratio"] == 0.0
    assert stats["pos_entity_seen_positive_ratio"] == 0.0
    assert stats["pos_entity_seen_ratio"] == 0.0


def test_outside_pool_excluded() -> None:
    entities: list[tuple[str, str, int, list[str]]] = [
        ("B001", "I1", 1, ["202401", "202402"]),
        ("B002", "I1", 0, ["202401"]),
    ]
    for i in range(50):
        entities.append((f"B{i+10:03d}", "I1", i % 5 == 0, ["202401", "202402", "202403"]))
    entities.append(("B999", "I9", 0, ["202301"]))  # pool 밖
    df = _panel_df(entities)
    train_m, test_m = group_random_split_masks(
        df,
        pool_start="202401",
        pool_end="202412",
        test_size=0.3,
        random_state=7,
    )
    outside = df["CRTR_YM"] == "202301"
    assert not bool(train_m[outside].any())
    assert not bool(test_m[outside].any())


def test_all_rows_of_entity_same_side() -> None:
    entities = []
    for i in range(55):
        label = 1 if i < 12 else 0
        entities.append((f"B{i:03d}", f"I{i % 4}", label, ["202401", "202402", "202403"]))
    df = _panel_df(entities)
    train_m, test_m = group_random_split_masks(
        df,
        test_size=0.3,
        random_state=99,
    )
    for _, row in df.iterrows():
        key = (row["PFM_BIZ_ID"], row["INST_ID"])
        same_key = (df["PFM_BIZ_ID"] == key[0]) & (df["INST_ID"] == key[1])
        sides = set()
        if bool(train_m[same_key].any()):
            sides.add("train")
        if bool(test_m[same_key].any()):
            sides.add("test")
        assert len(sides) == 1


def test_stratified_positive_entity_share() -> None:
    """층화 시 Test 양성 엔티티 비율이 test_size 에 근접."""
    entities = []
    for i in range(100):
        label = 1 if i < 30 else 0
        entities.append((f"B{i:03d}", "I1", label, ["202401", "202402"]))
    df = _panel_df(entities)
    train_m, test_m = group_random_split_masks(
        df,
        test_size=0.3,
        random_state=42,
    )
    stats = _overlap_stats(df, train_m, test_m)
    n_test_pos = stats["n_pos_entities_test"]
    n_pos = stats["n_pos_entities"]
    share = n_test_pos / n_pos if n_pos else 0.0
    assert 0.15 <= share <= 0.45


def test_too_few_pool_rows_raises() -> None:
    df = _panel_df([("B001", "I1", 0, ["202401"])])
    try:
        group_random_split_masks(df, pool_start="202401", pool_end="202412")
    except RuntimeError as exc:
        assert "풀 행 수 부족" in str(exc)
    else:
        raise AssertionError("RuntimeError expected")


def test_drop_rows_missing_group_keys() -> None:
    df = pd.DataFrame(
        {
            "CRTR_YM": ["202401", None, "202403", "202404"],
            "PFM_BIZ_ID": ["B1", "B2", None, "B4"],
            "INST_ID": ["I1", "I2", None, "I4"],
            "TAET_YN": ["N", "N", "Y", "N"],
        }
    )
    df2, info = drop_rows_missing_group_keys(df)
    assert info["n_rows_dropped"] == 2
    assert info["n_rows_after"] == 2
    assert info["key_columns_checked"] == ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    assert list(df2["PFM_BIZ_ID"]) == ["B1", "B4"]


def test_drop_rows_missing_crtr_ym_only() -> None:
    df = pd.DataFrame(
        {
            "CRTR_YM": ["202401", None],
            "PFM_BIZ_ID": ["B1", "B2"],
            "INST_ID": ["I1", "I2"],
            "TAET_YN": ["N", "N"],
        }
    )
    _, info = drop_rows_missing_group_keys(df)
    assert info["n_rows_dropped"] == 1
    assert info["n_rows_after"] == 1


def test_group_overlap_after_dropping_missing_keys() -> None:
    entities = [("B001", "I1", 1, ["202401", "202402"]), ("B002", None, 0, ["202401"])]
    df = _panel_df(entities)
    df2, info = drop_rows_missing_group_keys(df)
    assert info["n_rows_dropped"] == 1
    train_m = pd.Series([True, False])
    test_m = pd.Series([False, True])
    stats = group_overlap_stats(
        df2,
        "PFM_BIZ_ID+INST_ID",
        encode_target(df2["TAET_YN"], "Y"),
        train_m.to_numpy(),
        test_m.to_numpy(),
    )
    assert stats["n_rows"] == 2


def test_align_labeled_to_split_masks() -> None:
    """03에서 PK 제외 후 저장된 split_masks(짧은 길이)와 labeled(원본)를 맞춘다."""
    df = pd.DataFrame(
        {
            "CRTR_YM": ["202401", None, "202403"],
            "PFM_BIZ_ID": ["B1", "B2", "B3"],
            "INST_ID": ["I1", "I2", "I3"],
            "TAET_YN": ["N", "N", "Y"],
        }
    )
    train_m = np.array([True, False])
    test_m = np.array([False, True])
    df2, tr, te, info = align_labeled_to_split_masks(df, train_m, test_m)
    assert info["n_rows_dropped"] == 1
    assert len(df2) == 2
    assert tr.tolist() == [True, False]
    assert te.tolist() == [False, True]


def test_drop_rows_missing_group_keys_all_null_raises_empty() -> None:
    df = pd.DataFrame(
        {
            "CRTR_YM": [None, None],
            "PFM_BIZ_ID": ["B1", None],
            "INST_ID": ["I1", "I2"],
        }
    )
    df2, info = drop_rows_missing_group_keys(df)
    assert info["n_rows_after"] == 0
    assert len(df2) == 0


def test_missing_group_column_raises() -> None:
    df = pd.DataFrame({"CRTR_YM": ["202401"], "TAET_YN": ["N"]})
    try:
        group_random_split_masks(df)
    except KeyError:
        pass
    else:
        raise AssertionError("KeyError expected")
