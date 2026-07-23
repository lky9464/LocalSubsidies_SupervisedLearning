"""08 ranking policy unit tests."""

from __future__ import annotations

from src.pipeline.ranking import (
    _compare_rows,
    build_model_ranking,
    ranking_config,
)


def _summary(lift_a: float, pr_a: float, lift_b: float, pr_b: float) -> dict:
    def block(lift: float, pr: float) -> tuple[dict, dict]:
        return (
            {"PR_AUC(AveragePrecision)": pr, "F1점수(F1)": 0.5},
            {"상위1%리프트(top_1pct_lift)": lift},
        )

    m1, l1 = block(lift_a, pr_a)
    m2, l2 = block(lift_b, pr_b)
    return {
        "metrics": {"algo_a": m1, "algo_b": m2},
        "lift": {"algo_a": l1, "algo_b": l2},
    }


def test_lift_material_difference_wins_over_pr_auc():
    rc = ranking_config(None)
    row_a = {"top1_lift": 8.5, "pr_auc": 0.96}
    row_b = {"top1_lift": 8.0, "pr_auc": 0.99}
    assert _compare_rows(row_a, row_b, rc) == 1


def test_lift_close_uses_pr_auc():
    rc = ranking_config(None)
    row_a = {"top1_lift": 8.20, "pr_auc": 0.968}
    row_b = {"top1_lift": 8.00, "pr_auc": 0.974}
    assert _compare_rows(row_a, row_b, rc) == -1


def test_both_close_is_tie():
    rc = ranking_config(None)
    row_a = {"top1_lift": 8.00, "pr_auc": 0.970}
    row_b = {"top1_lift": 8.02, "pr_auc": 0.971}
    assert _compare_rows(row_a, row_b, rc) == 0


def test_build_ranking_roles_and_low_confidence():
    summary = _summary(8.0, 0.970, 8.01, 0.971)
    ranking, meta = build_model_ranking(
        summary, algorithms=["algo_a", "algo_b"], cfg={}
    )
    assert len(ranking) == 2
    roles = {r["algo"]: r["role"] for r in ranking}
    assert roles["algo_a"] in ("primary", "aux")
    assert roles["algo_b"] in ("primary", "aux")
    assert meta["ranking_confidence"] == "low"


def test_primary_guard_skips_weak_pr_auc():
    summary = {
        "metrics": {
            "strong_lift": {
                "PR_AUC(AveragePrecision)": 0.90,
            },
            "strong_pr": {
                "PR_AUC(AveragePrecision)": 0.97,
            },
        },
        "lift": {
            "strong_lift": {"상위1%리프트(top_1pct_lift)": 10.0},
            "strong_pr": {"상위1%리프트(top_1pct_lift)": 8.0},
        },
    }
    ranking, meta = build_model_ranking(
        summary,
        algorithms=["strong_lift", "strong_pr"],
        cfg={"ranking": {"primary_pr_auc_abs_gap": 0.01, "primary_pr_auc_rel_gap_pct": 3.0}},
    )
    primary = next(r for r in ranking if r["role"] == "primary")
    assert primary["algo"] == "strong_pr"
    assert meta["ranking_confidence"] == "low"
