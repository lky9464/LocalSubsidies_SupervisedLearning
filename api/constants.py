"""Shared constants (no Streamlit dependency)."""

from __future__ import annotations

ALGO_LABELS = {
    "catboost": "CatBoost",
    "stacked_ensemble": "Stacked Ensemble",
    "easy_ensemble": "EasyEnsemble",
    "gradient_boosting": "Gradient Boosting",
    "random_forest": "RandomForest",
}

PREVIEW_OPTIONS = (10, 30, 50, 100)

METRIC_HELP = {
    "상위N%리프트": (
        "상위 N% 구간의 실제 양성 비율을 전체 양성 비율로 나눈 값입니다. "
        "예: 리프트 10 → 무작위로 고를 때보다 양성(타겟)이 약 10배 많이 포함됩니다."
    ),
    "상위N%양성비중": (
        "상위 N% 안에 실제 양성(타겟)이 차지하는 비율입니다 "
        "(precision@topN%). 높을수록 우선 점검 구간의 적중률이 좋습니다."
    ),
    "상위N%양성포착": (
        "전체 양성(타겟) 중 상위 N%에 포함된 비율입니다 "
        "(recall@topN%). 높을수록 실제 위험 건을 상위 구간에서 많이 잡아냅니다."
    ),
}

COMPARE_COLUMNS = [
    "순위",
    "알고리즘",
    "역할",
    "PR-AUC",
    "ROC-AUC",
    "F1",
    "상위1%리프트",
    "상위1%양성비중",
    "상위1%양성포착",
    "상위5%리프트",
    "상위5%양성비중",
    "상위5%양성포착",
]
