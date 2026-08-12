"""score_distribution — bins · slim load · cache."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.scoring.ops_queue import ACTUAL_COL
from src.scoring.score_table import SCORE_COL
from src.scoring.score_distribution import (
    aggregate_entity_single_score,
    compute_score_distribution,
    get_or_build_score_distribution_payload,
    load_test_scores_slim,
    read_score_distribution_cache,
    score_bin_labels,
    score_distribution_cache_path,
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


def test_slim_load_and_cache(tmp_path: Path):
    csv_path = tmp_path / "algo_test_scores.csv"
    wide = pd.DataFrame(
        {
            "CRTR_YM": ["202501", "202501"],
            "PFM_BIZ_ID": ["B1", "B2"],
            "INST_ID": ["I1", "I2"],
            SCORE_COL: ["100", "900"],
            ACTUAL_COL: ["0", "1"],
            "기여도TOP01_큰열(BIG)": ["x" * 20, "y" * 20],
            "불필요열": ["a", "b"],
        }
    )
    wide.to_csv(csv_path, index=False, encoding="EUC-KR")

    slim = load_test_scores_slim(
        csv_path,
        "EUC-KR",
        entity_keys=("PFM_BIZ_ID", "INST_ID"),
    )
    assert slim is not None
    assert "불필요열" not in slim.columns
    assert SCORE_COL in slim.columns

    cfg = {"split": {"group_key": "PFM_BIZ_ID+INST_ID"}, "encoding": "EUC-KR"}
    payload = get_or_build_score_distribution_payload(csv_path, cfg)
    assert payload is not None
    assert payload["pk"]["total"] == 2
    assert score_distribution_cache_path(csv_path).exists()

    cached = read_score_distribution_cache(csv_path)
    assert cached is not None
    assert cached["pk"]["total"] == 2
    again = get_or_build_score_distribution_payload(csv_path, cfg)
    assert again == cached
