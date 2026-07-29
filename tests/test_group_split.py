"""group_random_split_masks 단위 테스트 (합성 패널, 실데이터 미사용)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.group_audit import group_overlap_stats
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


def test_missing_group_column_raises() -> None:
    df = pd.DataFrame({"CRTR_YM": ["202401"], "TAET_YN": ["N"]})
    try:
        group_random_split_masks(df)
    except KeyError:
        pass
    else:
        raise AssertionError("KeyError expected")
