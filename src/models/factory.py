"""알고리즘별 분류기 생성 (16GB RAM 친화 기본값)."""

from __future__ import annotations

from typing import Any

ALGORITHM_NAMES = [
    "catboost",
    "stacked_ensemble",
    "easy_ensemble",
    "gradient_boosting",
    "random_forest",
]

# 병렬 과다 시 메모리 폭증 방지 (Ryzen 3 / 16GB)
_N_JOBS = 2

# 진행률 표시용 메타
_PROGRESS_INFO = {
    "catboost": {"iterations": 400},
    "random_forest": {"n_estimators": 200},
    "gradient_boosting": {"max_iter": 300},
    "stacked_ensemble": {"cv": 3, "base": ["rf", "hgb"]},
    "easy_ensemble": {"n_estimators": 8},
}


def get_model_progress_info(name: str) -> dict[str, Any]:
    return dict(_PROGRESS_INFO.get(name.lower().strip(), {}))


def build_model(
    name: str,
    random_seed: int = 42,
    cat_features: list[str] | None = None,
    show_progress: bool = False,
) -> Any:
    """이름으로 모델 인스턴스를 생성한다."""
    name = name.lower().strip()
    # sklearn verbose: 0=무음, 1+=내부 진행 로그
    verb = 1 if show_progress else 0

    if name == "catboost":
        from catboost import CatBoostClassifier

        # verbose는 fit(callbacks=...)로 제어. 생성 시에는 끔.
        return CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            random_seed=random_seed,
            verbose=False,
            auto_class_weights="Balanced",
            cat_features=cat_features or [],
            thread_count=_N_JOBS,
            depth=6,
            iterations=_PROGRESS_INFO["catboost"]["iterations"],
            learning_rate=0.05,
            allow_writing_files=False,
        )

    if name == "random_forest":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=_PROGRESS_INFO["random_forest"]["n_estimators"],
            max_depth=20,
            min_samples_leaf=5,
            n_jobs=_N_JOBS,
            class_weight="balanced",
            random_state=random_seed,
            verbose=verb,
        )

    if name == "gradient_boosting":
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            max_depth=6,
            learning_rate=0.05,
            max_iter=_PROGRESS_INFO["gradient_boosting"]["max_iter"],
            random_state=random_seed,
            class_weight="balanced",
            max_bins=128,
            verbose=verb,
        )

    if name == "stacked_ensemble":
        from sklearn.ensemble import (
            HistGradientBoostingClassifier,
            RandomForestClassifier,
            StackingClassifier,
        )
        from sklearn.linear_model import LogisticRegression

        estimators = [
            (
                "rf",
                RandomForestClassifier(
                    n_estimators=100,
                    max_depth=16,
                    min_samples_leaf=5,
                    n_jobs=1,
                    class_weight="balanced",
                    random_state=random_seed,
                    verbose=0,
                ),
            ),
            (
                "hgb",
                HistGradientBoostingClassifier(
                    max_depth=5,
                    learning_rate=0.05,
                    max_iter=150,
                    random_state=random_seed,
                    class_weight="balanced",
                    max_bins=128,
                    verbose=verb,
                ),
            ),
        ]
        return StackingClassifier(
            estimators=estimators,
            final_estimator=LogisticRegression(
                max_iter=500,
                class_weight="balanced",
                random_state=random_seed,
                verbose=verb,
            ),
            passthrough=False,
            cv=3,
            n_jobs=1,
            verbose=verb,
        )

    if name == "easy_ensemble":
        from imblearn.ensemble import EasyEnsembleClassifier

        return EasyEnsembleClassifier(
            n_estimators=_PROGRESS_INFO["easy_ensemble"]["n_estimators"],
            random_state=random_seed,
            n_jobs=1,
            verbose=verb,
        )

    raise ValueError(f"알 수 없는 알고리즘: {name}. 지원={ALGORITHM_NAMES}")
