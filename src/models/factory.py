"""알고리즘별 분류기 생성 (16GB RAM 친화 기본값).

algo_id = {family}_v{N}. 하이퍼파라미터는 configs model_params[algo_id].
"""

from __future__ import annotations

from typing import Any

from src.models.registry import (
    DEFAULT_ALGO_IDS,
    family_of,
    list_algo_ids,
    normalize_algo_id,
)

ALGORITHM_NAMES = list(DEFAULT_ALGO_IDS)

# 병렬 과다 시 메모리 폭증 방지 (Ryzen 3 / 16GB)
_N_JOBS = 2

# family 단위 폴백 (버전 키가 없을 때)
_DEFAULT_MODEL_PARAMS: dict[str, dict[str, Any]] = {
    "catboost": {
        "iterations": 400,
        "depth": 6,
        "learning_rate": 0.05,
        "auto_class_weights": "Balanced",
    },
    "random_forest": {
        "n_estimators": 200,
        "max_depth": 20,
        "min_samples_leaf": 5,
        "class_weight": "balanced",
    },
    "gradient_boosting": {
        "max_iter": 300,
        "max_depth": 6,
        "learning_rate": 0.05,
        "max_bins": 128,
        "class_weight": "balanced",
    },
    "stacked_ensemble": {
        "cv": 3,
        "rf_n_estimators": 100,
        "rf_max_depth": 16,
        "rf_min_samples_leaf": 5,
        "hgb_max_depth": 5,
        "hgb_learning_rate": 0.05,
        "hgb_max_iter": 150,
        "hgb_max_bins": 128,
        "meta_max_iter": 500,
    },
    "easy_ensemble": {
        "n_estimators": 8,
    },
}


def registered_algo_ids(cfg: dict[str, Any] | None = None) -> list[str]:
    return list_algo_ids(cfg)


def resolve_model_params(
    cfg: dict[str, Any] | None,
    name: str,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """family 기본 → model_params[algo_id] → override."""
    algo_id = normalize_algo_id(name)
    family = family_of(algo_id)
    base = dict(_DEFAULT_MODEL_PARAMS.get(family, {}))
    if cfg:
        mp = cfg.get("model_params") or {}
        # 구 키(family) 호환
        if isinstance(mp.get(family), dict):
            base.update(mp[family])
        if isinstance(mp.get(algo_id), dict):
            base.update(mp[algo_id])
    if override:
        base.update(override)
    return base


def get_model_progress_info(
    name: str,
    cfg: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    algo_id = normalize_algo_id(name)
    family = family_of(algo_id)
    p = params if params is not None else resolve_model_params(cfg, algo_id)
    if family == "catboost":
        return {"iterations": int(p.get("iterations", 400))}
    if family == "random_forest":
        return {"n_estimators": int(p.get("n_estimators", 200))}
    if family == "gradient_boosting":
        return {"max_iter": int(p.get("max_iter", 300))}
    if family == "stacked_ensemble":
        return {"cv": int(p.get("cv", 3)), "base": ["rf", "hgb"]}
    if family == "easy_ensemble":
        return {"n_estimators": int(p.get("n_estimators", 8))}
    return {}


def build_model(
    name: str,
    random_seed: int = 42,
    cat_features: list[str] | None = None,
    show_progress: bool = False,
    params: dict[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
    n_jobs: int | None = None,
) -> Any:
    """algo_id(또는 구 family명)로 모델 인스턴스 생성."""
    algo_id = normalize_algo_id(name)
    family = family_of(algo_id)
    verb = 1 if show_progress else 0
    p = resolve_model_params(cfg, algo_id, params)
    jobs = _N_JOBS
    if cfg and cfg.get("memory", {}).get("n_jobs") is not None:
        jobs = int(cfg["memory"]["n_jobs"])
    if n_jobs is not None:
        jobs = int(n_jobs)

    if family == "catboost":
        from catboost import CatBoostClassifier

        return CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="AUC",
            random_seed=random_seed,
            verbose=False,
            auto_class_weights=p.get("auto_class_weights", "Balanced"),
            cat_features=cat_features or [],
            thread_count=jobs,
            depth=int(p.get("depth", 6)),
            iterations=int(p.get("iterations", 400)),
            learning_rate=float(p.get("learning_rate", 0.05)),
            allow_writing_files=False,
        )

    if family == "random_forest":
        from sklearn.ensemble import RandomForestClassifier

        return RandomForestClassifier(
            n_estimators=int(p.get("n_estimators", 200)),
            max_depth=int(p.get("max_depth", 20)),
            min_samples_leaf=int(p.get("min_samples_leaf", 5)),
            n_jobs=jobs,
            class_weight=p.get("class_weight", "balanced"),
            random_state=random_seed,
            verbose=verb,
        )

    if family == "gradient_boosting":
        from sklearn.ensemble import HistGradientBoostingClassifier

        return HistGradientBoostingClassifier(
            max_depth=int(p.get("max_depth", 6)),
            learning_rate=float(p.get("learning_rate", 0.05)),
            max_iter=int(p.get("max_iter", 300)),
            random_state=random_seed,
            class_weight=p.get("class_weight", "balanced"),
            max_bins=int(p.get("max_bins", 128)),
            verbose=verb,
        )

    if family == "stacked_ensemble":
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
                    n_estimators=int(p.get("rf_n_estimators", 100)),
                    max_depth=int(p.get("rf_max_depth", 16)),
                    min_samples_leaf=int(p.get("rf_min_samples_leaf", 5)),
                    n_jobs=1,
                    class_weight="balanced",
                    random_state=random_seed,
                    verbose=0,
                ),
            ),
            (
                "hgb",
                HistGradientBoostingClassifier(
                    max_depth=int(p.get("hgb_max_depth", 5)),
                    learning_rate=float(p.get("hgb_learning_rate", 0.05)),
                    max_iter=int(p.get("hgb_max_iter", 150)),
                    random_state=random_seed,
                    class_weight="balanced",
                    max_bins=int(p.get("hgb_max_bins", 128)),
                    verbose=verb,
                ),
            ),
        ]
        return StackingClassifier(
            estimators=estimators,
            final_estimator=LogisticRegression(
                max_iter=int(p.get("meta_max_iter", 500)),
                class_weight="balanced",
                random_state=random_seed,
                verbose=verb,
            ),
            passthrough=False,
            cv=int(p.get("cv", 3)),
            n_jobs=1,
            verbose=verb,
        )

    if family == "easy_ensemble":
        from imblearn.ensemble import EasyEnsembleClassifier

        return EasyEnsembleClassifier(
            n_estimators=int(p.get("n_estimators", 8)),
            random_state=random_seed,
            n_jobs=1,
            verbose=verb,
        )

    raise ValueError(f"알 수 없는 알고리즘: {name}. 지원={ALGORITHM_NAMES}")
