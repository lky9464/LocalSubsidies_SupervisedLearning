"""score_distribution — bins · feature charts."""

from __future__ import annotations

import pandas as pd

from src.scoring.ops_queue import ACTUAL_COL, SCORE_COL
from src.scoring.score_distribution import (
    aggregate_entity_single_score,
    build_categorical_feature_distribution,
    build_numeric_feature_distribution,
    compute_score_distribution,
    resolve_feature_kind,
    score_bin_labels,
)


def test_score_bin_labels_ten():
    assert len(score_bin_labels()) == 10
    assert score_bin_labels()[0] == "0-100"
    assert score_bin_labels()[-1] == "900-1000"


def test_compute_score_distribution_pk():
    rows = []
    for i in range(100):
        rows.append(
            {
                SCORE_COL: i * 10,
                ACTUAL_COL: "1" if i >= 90 else "0",
            }
        )
    df = pd.DataFrame(rows)
    out = compute_score_distribution(df)
    assert out["total"] == 100
    assert sum(b["total"] for b in out["bins"]) == 100
    assert sum(b["target"] for b in out["bins"]) == 10


def test_entity_aggregate_and_bins():
    rows = []
    for i in range(4):
        e = i // 2
        rows.append(
            {
                "CRTR_YM": f"2025{e:02d}{i % 2}",
                "PFM_BIZ_ID": f"B{e}",
                "INST_ID": f"I{e}",
                SCORE_COL: str(100 + i * 50),
                ACTUAL_COL: "1" if i < 2 else "0",
            }
        )
    df = pd.DataFrame(rows)
    ent = aggregate_entity_single_score(df, ("PFM_BIZ_ID", "INST_ID"))
    assert len(ent) == 2
    dist = compute_score_distribution(ent)
    assert dist["total"] == 2


def test_numeric_and_categorical_feature():
    df = pd.DataFrame(
        {
            SCORE_COL: [100, 200, 300, 400],
            "기여도TOP01_수치(FNUM)": ["1", "2", "3", "4"],
            "기여도TOP02_코드(CD)": ["A", "A", "B", "C"],
        }
    )
    num = build_numeric_feature_distribution(df, feature_col="기여도TOP01_수치(FNUM)", max_points=10)
    assert len(num["scatter"]) == 4
    assert len(num["regression"]["points"]) > 0

    cat = build_categorical_feature_distribution(df, feature_col="기여도TOP02_코드(CD)")
    assert len(cat["bars"]) >= 2

    cfg = {"categorical_candidates": ["CD"]}
    assert resolve_feature_kind("CD", cfg, df["기여도TOP02_코드(CD)"]) == "categorical"
