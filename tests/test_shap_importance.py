"""SHAP 전역 중요도 산출 단위 테스트 (합성 데이터)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.datasets import make_classification
from sklearn.ensemble import RandomForestClassifier

from src.evaluate.shap_importance import (
    build_shap_total_dataframe,
    compute_shap_total,
    write_shap_total_xlsx,
)


@pytest.fixture(scope="module")
def shap_available() -> None:
    pytest.importorskip("shap")


def test_build_shap_total_dataframe_direction_and_share(shap_available) -> None:
    feature_names = ["F_A", "F_B", "F_C"]
    mean_abs = np.array([0.6, 0.3, 0.1], dtype=float)
    mean_signed = np.array([0.6, -0.3, 0.0], dtype=float)
    comments = {"F_A": "변수A", "F_B": "변수B", "F_C": "변수C"}

    df = build_shap_total_dataframe(
        "random_forest_v1",
        feature_names,
        mean_abs,
        mean_signed,
        comments,
        method="shap_tree_explainer",
        n_samples=100,
    )

    assert len(df) == 3
    assert df.iloc[0]["피처명(feature)"] == "F_A"
    assert df["기여도비중(importance_share)"].sum() == pytest.approx(1.0)

    row_b = df[df["피처명(feature)"] == "F_B"].iloc[0]
    assert row_b["기여방향(direction)"] == "-"
    assert row_b["기여방향표시(direction_label)"] == "음(-)"

    row_c = df[df["피처명(feature)"] == "F_C"].iloc[0]
    assert row_c["기여방향(direction)"] == "0"
    assert row_c["기여방향표시(direction_label)"] == "중립(0)"


def test_compute_shap_total_random_forest(shap_available) -> None:
    X, y = make_classification(
        n_samples=200,
        n_features=6,
        n_informative=4,
        n_redundant=0,
        random_state=42,
    )
    model = RandomForestClassifier(
        n_estimators=20,
        max_depth=4,
        random_state=42,
        n_jobs=1,
    )
    model.fit(X, y)
    feature_names = [f"F{i}" for i in range(X.shape[1])]

    df = compute_shap_total(
        "random_forest_v1",
        model,
        feature_names,
        X,
        y,
        {},
        sample_size=100,
    )

    assert len(df) == X.shape[1]
    assert "기여도비중(importance_share)" in df.columns
    assert "기여방향(direction)" in df.columns
    assert "기여방향표시(direction_label)" in df.columns
    assert set(df["기여방향(direction)"].unique()) <= {"+", "-", "0"}


def test_write_shap_total_xlsx(shap_available) -> None:
    df = pd.DataFrame(
        [
            {
                "순위(rank)": 1,
                "알고리즘(algorithm)": "random_forest_v1",
                "피처명(feature)": "F_A",
                "피처명한글(feature_ko)": "변수A",
                "기여도비중(importance_share)": 1.0,
                "기여도원점수(importance_raw)": 0.5,
                "평균SHAP부호(mean_shap_signed)": 0.5,
                "기여방향(direction)": "+",
                "기여방향표시(direction_label)": "양(+)",
                "측정방법(method)": "shap_tree_explainer",
                "표본수(n_samples)": 10,
                "사유(reason)": "test",
            }
        ]
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "SHAP_total.xlsx"
        write_shap_total_xlsx(path, df)
        assert path.exists()
        loaded = pd.read_excel(path, sheet_name="전체(all)")
        assert loaded.iloc[0]["피처명(feature)"] == "F_A"
        guide = pd.read_excel(path, sheet_name="안내(guide)")
        assert "기여방향" in guide.iloc[0]["안내"]
