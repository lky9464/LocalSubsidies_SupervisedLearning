"""inference_capture — 3케이스 · entity · case availability."""

from __future__ import annotations

import pandas as pd

from src.scoring.inference_capture import (
    _case_inference_dfs,
    build_inference_capture_queues,
)
from src.scoring.ops_capture import (
    CASE_AUX_REF,
    CASE_PRIMARY_AUX,
    CASE_PRIMARY_REF,
    OPS_PAIR_SPECS,
    build_ops_pair_queue,
)
from src.scoring.ops_queue import SCORE_COL
from tests.test_ops_capture import _make_score_df


def test_build_inference_capture_primary_aux_only():
    ops_cfg = {"a_top_pct": 1, "b_top_pct": 5, "c_top_pct": 10}
    spec = OPS_PAIR_SPECS[0]
    roles = {"primary": "rf", "aux": "cb", "reference": "st"}
    infer_algos = ["rf", "cb"]
    scores = {
        "rf": _make_score_df(50, 900.0),
        "cb": _make_score_df(50, 800.0),
    }
    row_df, col_df, err = _case_inference_dfs(spec, scores, roles, infer_algos)
    assert err is None
    assert row_df is not None and col_df is not None
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    q = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
    assert len(q) == 50


def test_case_unavailable_when_reference_not_inferred():
    spec = next(s for s in OPS_PAIR_SPECS if s.case_id == CASE_PRIMARY_REF)
    roles = {"primary": "rf", "aux": "cb", "reference": "st"}
    infer_algos = ["rf", "cb"]
    scores = {"rf": _make_score_df(10, 900.0), "cb": _make_score_df(10, 800.0), "st": _make_score_df(10, 700.0)}
    _, _, err = _case_inference_dfs(spec, scores, roles, infer_algos)
    assert err is not None
    assert "주·참" in err


def test_case_unavailable_no_reference_role():
    spec = next(s for s in OPS_PAIR_SPECS if s.case_id == CASE_AUX_REF)
    roles = {"primary": "rf", "aux": "cb", "reference": None}
    infer_algos = ["rf", "cb"]
    scores = {"rf": _make_score_df(10, 900.0), "cb": _make_score_df(10, 800.0)}
    _, _, err = _case_inference_dfs(spec, scores, roles, infer_algos)
    assert err is not None


def test_build_inference_capture_queues_integration():
    """build_inference_capture_queues — mock 없이 DataFrame만."""
    ops_cfg = {"a_top_pct": 50, "b_top_pct": 80, "c_top_pct": 100}
    keys = ["CRTR_YM", "PFM_BIZ_ID", "INST_ID"]
    pk_queues = []
    entity_queues = []
    for spec in OPS_PAIR_SPECS[:1]:
        row_df = _make_score_df(20, 100.0)
        col_df = _make_score_df(20, 90.0)
        pk_q = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
        pk_queues.append(pk_q)
    assert len(pk_queues) == 1
    assert pk_queues[0].iloc[0]["케이스(case_id)"] == CASE_PRIMARY_AUX
