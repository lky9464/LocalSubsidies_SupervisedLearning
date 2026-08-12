"""ops_capture — pair queue · entity aggregate."""

from __future__ import annotations

import pandas as pd
import pytest

from src.scoring.ops_capture import (
    CASE_PRIMARY_AUX,
    OPS_PAIR_SPECS,
    aggregate_entity_queue,
    build_ops_pair_queue,
    priority_from_pair,
    summarize_matrix_for,
)
from src.scoring.ops_queue import ACTUAL_COL, PRED_COL, SCORE_COL


def _make_score_df(
    n: int,
    base_score: float,
    *,
    ym: str = "202501",
    entity_pairs: int | None = None,
) -> pd.DataFrame:
    """PK 키(CRTR_YM·PFM_BIZ_ID·INST_ID)는 행마다 유일. entity_pairs=k이면 k 엔티티×2행."""
    rows = []
    for i in range(n):
        if entity_pairs is not None:
            ent_i = i // 2
            biz, inst = f"B{ent_i}", f"I{ent_i}"
            row_ym = f"{ym}{ent_i:02d}{i % 2}"
        else:
            biz, inst = f"B{i}", f"I{i}"
            row_ym = ym if n == 1 else f"{ym}{i:04d}"
        rows.append(
            {
                "CRTR_YM": row_ym,
                "PFM_BIZ_ID": biz,
                "INST_ID": inst,
                SCORE_COL: str(base_score - i),
                ACTUAL_COL: "1" if i < 2 else "0",
                PRED_COL: "0",
            }
        )
    return pd.DataFrame(rows)


def test_build_ops_pair_queue_primary_aux():
    ops_cfg = {"a_top_pct": 1, "b_top_pct": 5, "c_top_pct": 10}
    spec = OPS_PAIR_SPECS[0]
    row_df = _make_score_df(100, 900.0)
    col_df = _make_score_df(100, 800.0)
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    q = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
    assert len(q) == 100
    assert q.iloc[0]["케이스(case_id)"] == CASE_PRIMARY_AUX
    assert priority_from_pair("주A", "보A", spec) == 1


def test_entity_aggregate_any_positive_and_round():
    ops_cfg = {"a_top_pct": 50, "b_top_pct": 80, "c_top_pct": 100}
    spec = OPS_PAIR_SPECS[0]
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    row_df = _make_score_df(4, 100.0, entity_pairs=2)
    col_df = _make_score_df(4, 90.0, entity_pairs=2)
    pk = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
    ent = aggregate_entity_queue(pk, ("PFM_BIZ_ID", "INST_ID"), ops_cfg, spec)
    assert len(ent) == 2
    assert "CRTR_YM" not in ent.columns
    assert ent[ACTUAL_COL].max() in ("1", 1)


def test_entity_aggregate_blank_actual_stays_blank():
    """추론처럼 실제라벨 공란이면 엔티티 집계도 0이 아니라 공란."""
    ops_cfg = {"a_top_pct": 50, "b_top_pct": 80, "c_top_pct": 100}
    spec = OPS_PAIR_SPECS[0]
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    row_df = _make_score_df(4, 100.0, entity_pairs=2)
    col_df = _make_score_df(4, 90.0, entity_pairs=2)
    row_df[ACTUAL_COL] = ""
    col_df[ACTUAL_COL] = ""
    pk = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
    ent = aggregate_entity_queue(
        pk, ("PFM_BIZ_ID", "INST_ID"), ops_cfg, spec, preserve_blank_actual=True
    )
    assert len(ent) == 2
    assert ACTUAL_COL in ent.columns
    for v in ent[ACTUAL_COL]:
        assert v == "" or (isinstance(v, float) and pd.isna(v))

    # Test 기본 경로: 공란이어도 any-positive → 0
    ent_test = aggregate_entity_queue(pk, ("PFM_BIZ_ID", "INST_ID"), ops_cfg, spec)
    assert set(int(x) for x in ent_test[ACTUAL_COL]) == {0}


def test_entity_aggregate_string_amount_columns():
    """점수 CSV dtype=str 로드 시 금액 열 mean 집계."""
    from src.scoring.score_table import FIXED_SCORE_EXTRA_COLUMNS

    ops_cfg = {"a_top_pct": 50, "b_top_pct": 80, "c_top_pct": 100}
    spec = OPS_PAIR_SPECS[0]
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    row_df = _make_score_df(4, 100.0, entity_pairs=2)
    col_df = _make_score_df(4, 90.0, entity_pairs=2)
    for src, header in FIXED_SCORE_EXTRA_COLUMNS:
        if "AMT" in src:
            row_df[header] = ["1000", "2000", "3000", "4000"]
        elif src == "PFM_BIZ_NM":
            row_df[header] = ["biz"] * 4
        elif src == "INST_NM":
            row_df[header] = ["inst"] * 4
    pk = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
    ent = aggregate_entity_queue(pk, ("PFM_BIZ_ID", "INST_ID"), ops_cfg, spec)
    assert len(ent) == 2
    amt_col = next(h for src, h in FIXED_SCORE_EXTRA_COLUMNS if "AMT" in src)
    assert pd.to_numeric(ent[amt_col], errors="coerce").notna().all()


def test_summarize_matrix_positive_filter():
    ops_cfg = {"a_top_pct": 50, "b_top_pct": 80, "c_top_pct": 100}
    spec = OPS_PAIR_SPECS[0]
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    pk = build_ops_pair_queue(
        _make_score_df(10, 50.0), _make_score_df(10, 40.0), keys, ops_cfg, spec
    )
    all_m = summarize_matrix_for(pk, spec, positive_only=False)
    pos_m = summarize_matrix_for(pk, spec, positive_only=True)
    assert int(all_m.to_numpy().sum()) == 10
    assert int(pos_m.to_numpy().sum()) <= int(all_m.to_numpy().sum())
