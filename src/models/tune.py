"""Validation 구간 하이퍼파라미터 소규모 탐색 (집계 지표만).

Test 구간은 사용하지 않는다. Cursor Agent는 본 모듈을 data_root와 함께 실행하지 말 것.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.evaluate.metrics import compute_classification_metrics, top_k_lift
from src.features.preprocess import encode_target, transform_features
from src.io.config import load_config, resolve_data_path, resolve_repo_path
from src.io.encoding_util import read_csv_auto
from src.models.factory import ALGORITHM_NAMES, build_model, resolve_model_params
from src.models.registry import family_of, normalize_algo_id


def _period_series(df: pd.DataFrame, col: str = "CRTR_YM") -> pd.Series:
    return df[col].astype(str).str.replace(r"\D", "", regex=True)


def fit_valid_masks_within_train(
    df: pd.DataFrame,
    train_mask: np.ndarray | pd.Series,
    *,
    valid_start: str,
    valid_end: str,
    period_col: str = "CRTR_YM",
) -> tuple[np.ndarray, np.ndarray]:
    """Train 마스크 안에서 valid 기간을 분리. fit = train & ~valid."""
    train_m = np.asarray(train_mask, dtype=bool)
    p = _period_series(df, period_col)
    valid_m = train_m & (p >= str(valid_start)) & (p <= str(valid_end))
    fit_m = train_m & ~valid_m
    return fit_m, valid_m


def fit_valid_masks_random_pool(
    df: pd.DataFrame,
    *,
    pool_start: str,
    pool_end: str,
    valid_size: float = 0.2,
    random_state: int = 42,
    period_col: str = "CRTR_YM",
) -> tuple[np.ndarray, np.ndarray]:
    """CRTR_YM 풀 구간에서 랜덤으로 fit/valid 분리 (튜닝 전용)."""
    from sklearn.model_selection import train_test_split

    p = _period_series(df, period_col)
    pool = ((p >= str(pool_start)) & (p <= str(pool_end))).to_numpy()
    idx = np.flatnonzero(pool)
    if len(idx) < 150:
        raise RuntimeError(
            f"튜닝 풀 행 수 부족: pool={len(idx)} ({pool_start}~{pool_end})."
        )
    fit_idx, valid_idx = train_test_split(
        idx,
        test_size=float(valid_size),
        random_state=int(random_state),
        shuffle=True,
    )
    fit_m = np.zeros(len(df), dtype=bool)
    valid_m = np.zeros(len(df), dtype=bool)
    fit_m[fit_idx] = True
    valid_m[valid_idx] = True
    return fit_m, valid_m


def resolve_tune_fit_valid(
    df: pd.DataFrame,
    train_mask: np.ndarray | pd.Series,
    cfg: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray, str]:
    """tune.split_mode 에 따라 fit/valid 마스크와 설명 문자열 반환."""
    tune_cfg = cfg.get("tune") or {}
    split_cfg = cfg.get("split") or {}
    mode = str(tune_cfg.get("split_mode") or "time").lower().strip()
    if mode == "random":
        pool_start = str(tune_cfg.get("pool_start") or "202401")
        pool_end = str(tune_cfg.get("pool_end") or "202512")
        valid_size = float(tune_cfg.get("valid_size", 0.2))
        rs = int(tune_cfg.get("random_state", cfg.get("random_seed", 42)))
        fit_m, valid_m = fit_valid_masks_random_pool(
            df,
            pool_start=pool_start,
            pool_end=pool_end,
            valid_size=valid_size,
            random_state=rs,
        )
        desc = (
            f"mode=random pool={pool_start}~{pool_end} "
            f"valid_size={valid_size} seed={rs}"
        )
        return fit_m, valid_m, desc

    valid_start = str(
        tune_cfg.get("valid_start") or split_cfg.get("valid_start") or "202504"
    )
    valid_end = str(tune_cfg.get("valid_end") or split_cfg.get("valid_end") or "202506")
    fit_m, valid_m = fit_valid_masks_within_train(
        df, train_mask, valid_start=valid_start, valid_end=valid_end
    )
    desc = f"mode=time valid={valid_start}~{valid_end} (Train 내부, Test 미사용)"
    return fit_m, valid_m, desc


def expand_param_grid(grid: dict[str, list[Any]]) -> list[dict[str, Any]]:
    if not grid:
        return [{}]
    keys = list(grid.keys())
    values = [list(grid[k]) for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _predict_proba_positive(model: Any, X: Any) -> np.ndarray:
    proba = model.predict_proba(X)
    if getattr(proba, "ndim", 1) == 1:
        return np.asarray(proba, dtype=float)
    return np.asarray(proba[:, 1], dtype=float)


def score_candidate(
    y_true: np.ndarray,
    y_proba: np.ndarray,
    *,
    top_k_percents: list[float | int],
) -> dict[str, Any]:
    y_pred = (y_proba >= 0.5).astype(int)
    metrics = compute_classification_metrics(y_true, y_pred, y_proba)
    scores = np.round(y_proba * 1000).astype(int)
    lift = top_k_lift(y_true, scores, top_k_percents)
    return {
        "pr_auc": metrics.get("PR_AUC(AveragePrecision)"),
        "roc_auc": metrics.get("ROC_AUC(ROC_AUC)"),
        "precision": metrics.get("정밀도(Precision)"),
        "recall": metrics.get("재현율(Recall)"),
        "f1": metrics.get("F1점수(F1)"),
        "top1_lift": lift.get("상위1%리프트(top_1pct_lift)"),
        "top5_lift": lift.get("상위5%리프트(top_5pct_lift)"),
        "top1_recall": lift.get("상위1%양성포착비율(top_1pct_recall)"),
        "top5_recall": lift.get("상위5%양성포착비율(top_5pct_recall)"),
    }


def _metric_key(row: dict[str, Any], key: str) -> float:
    v = row.get(key)
    if v is None:
        return float("-inf")
    return float(v)


def rank_candidates(
    rows: list[dict[str, Any]],
    *,
    baseline_precision: float | None,
    min_precision_ratio: float,
) -> list[dict[str, Any]]:
    """정밀도 가드 후 top1_lift → top5_lift → pr_auc 내림차순."""
    guarded: list[dict[str, Any]] = []
    for r in rows:
        prec = r.get("precision")
        ok = True
        if (
            baseline_precision is not None
            and baseline_precision > 0
            and prec is not None
            and float(prec) < float(baseline_precision) * float(min_precision_ratio)
        ):
            ok = False
        r = dict(r)
        r["precision_guard_pass"] = ok
        guarded.append(r)

    survivors = [r for r in guarded if r["precision_guard_pass"]] or guarded
    survivors_sorted = sorted(
        survivors,
        key=lambda r: (
            _metric_key(r, "top1_lift"),
            _metric_key(r, "top5_lift"),
            _metric_key(r, "pr_auc"),
        ),
        reverse=True,
    )
    # 탈락 후보도 리포트용으로 뒤에 붙임
    rejected = [r for r in guarded if not r["precision_guard_pass"]]
    return survivors_sorted + rejected


def tune_one_algorithm(
    algo: str,
    cfg: dict[str, Any],
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    """단일 알고리즘 격자 탐색. 집계 결과만 반환·저장."""
    algo = normalize_algo_id(algo)
    family = family_of(algo)
    if family not in ("random_forest", "catboost"):
        raise ValueError(
            f"튜닝 지원: random_forest_v*, catboost_v* (요청={algo}, family={family})"
        )

    import joblib

    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    labeled = interim / "labeled.csv"
    bundle_path = processed / "preprocess_bundle.joblib"
    masks_path = processed / "split_masks.joblib"
    for p in (labeled, bundle_path, masks_path):
        if not p.exists():
            raise FileNotFoundError(f"{p} 없음. 01~03을 먼저 실행하세요.")

    print(f"[tune] labeled 로드... ({algo})")
    df, used = read_csv_auto(labeled, candidates=cfg.get("encoding_candidates"))
    print(f"[tune] encoding={used}")
    bundle = joblib.load(bundle_path)
    masks = joblib.load(masks_path)
    train_m = masks["train_mask"]

    fit_m, valid_m, split_desc = resolve_tune_fit_valid(df, train_m, cfg)
    n_fit, n_valid = int(fit_m.sum()), int(valid_m.sum())
    if n_fit < 100 or n_valid < 50:
        raise RuntimeError(
            f"fit/valid 행 수 부족: fit={n_fit}, valid={n_valid}. ({split_desc})"
        )
    print(f"[tune] fit={n_fit:,} valid={n_valid:,} ({split_desc})")

    features = bundle["features"]
    categorical = bundle["categorical"]
    numeric = bundle["numeric"]
    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")
    seed = int(cfg.get("random_seed", 42))
    top_k = list((cfg.get("evaluation") or {}).get("top_k_percents") or [1, 5, 10])

    X_fit_raw = df.loc[fit_m, features].copy()
    X_val_raw = df.loc[valid_m, features].copy()
    y_fit = encode_target(df.loc[fit_m, target], pos)
    y_val = encode_target(df.loc[valid_m, target], pos)
    del df

    tune_cfg = cfg.get("tune") or {}
    grid = (tune_cfg.get("grids") or {}).get(algo) or (tune_cfg.get("grids") or {}).get(family) or {}
    base_params = resolve_model_params(cfg, algo)
    # 기준선(현재 model_params)을 첫 후보로 두고 격자 후보를 이어 붙임
    seen: set[tuple[tuple[str, str], ...]] = set()
    combos: list[dict[str, Any]] = []
    for delta in [{}] + expand_param_grid(grid):
        key = tuple(sorted((k, json.dumps(v, default=str)) for k, v in delta.items()))
        if key in seen:
            continue
        seen.add(key)
        combos.append(delta)

    print(f"[tune] 후보 수={len(combos)} (1번째는 현재 model_params 기준선)")
    rows: list[dict[str, Any]] = []

    for i, delta in enumerate(combos, start=1):
        params = {**base_params, **delta}
        if show_progress:
            print(f"[tune] [{i}/{len(combos)}] {algo} {delta or '(baseline)'}")

        if family == "catboost":
            pre = bundle["preprocessor_catboost"]
            X_tr, _ = transform_features(X_fit_raw, pre, categorical, numeric)
            X_va, _ = transform_features(X_val_raw, pre, categorical, numeric)
            model = build_model(
                algo,
                random_seed=seed,
                cat_features=categorical,
                cfg=cfg,
                params=params,
            )
            model.fit(X_tr, y_fit, cat_features=categorical, verbose=False)
        else:
            pre = bundle["preprocessor_sklearn"]
            X_tr, _ = transform_features(X_fit_raw, pre, categorical, numeric)
            X_va, _ = transform_features(X_val_raw, pre, categorical, numeric)
            model = build_model(
                algo,
                random_seed=seed,
                show_progress=False,
                cfg=cfg,
                params=params,
            )
            model.fit(X_tr, y_fit)

        y_proba = _predict_proba_positive(model, X_va)
        scored = score_candidate(np.asarray(y_val), y_proba, top_k_percents=top_k)
        row = {"algorithm": algo, "trial": i, "params": params, "delta": delta, **scored}
        rows.append(row)
        del model, X_tr, X_va

    baseline_precision = None
    for r in rows:
        if not r.get("delta"):
            baseline_precision = r.get("precision")
            break
    if baseline_precision is None and rows:
        baseline_precision = rows[0].get("precision")

    min_prec_ratio = float(tune_cfg.get("min_precision_ratio", 0.85))
    ranked = rank_candidates(
        rows,
        baseline_precision=baseline_precision,
        min_precision_ratio=min_prec_ratio,
    )
    best = ranked[0] if ranked else None

    out = {
        "algorithm": algo,
        "split_desc": split_desc,
        "fit_rows": n_fit,
        "valid_rows": n_valid,
        "baseline_precision": baseline_precision,
        "min_precision_ratio": min_prec_ratio,
        "best": best,
        "trials": ranked,
    }
    _save_tune_report(cfg, algo, out)
    return out


def _save_tune_report(cfg: dict[str, Any], algo: str, result: dict[str, Any]) -> Path:
    comp = resolve_repo_path(cfg, "reports_comparison")
    comp.mkdir(parents=True, exist_ok=True)
    json_path = comp / f"hyperparam_tune_{algo}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    flat_rows = []
    for t in result.get("trials") or []:
        flat = {
            "algorithm": t.get("algorithm"),
            "trial": t.get("trial"),
            "precision_guard_pass": t.get("precision_guard_pass"),
            "pr_auc": t.get("pr_auc"),
            "roc_auc": t.get("roc_auc"),
            "precision": t.get("precision"),
            "recall": t.get("recall"),
            "f1": t.get("f1"),
            "top1_lift": t.get("top1_lift"),
            "top5_lift": t.get("top5_lift"),
            "top1_recall": t.get("top1_recall"),
            "top5_recall": t.get("top5_recall"),
            "params_json": json.dumps(t.get("params") or {}, ensure_ascii=False),
        }
        flat_rows.append(flat)
    xlsx_path = comp / f"hyperparam_tune_{algo}.xlsx"
    pd.DataFrame(flat_rows).to_excel(xlsx_path, index=False)

    # best yaml 조각 (수동 병합용)
    best = result.get("best") or {}
    best_params = (best.get("params") or {}) if best else {}
    best_path = comp / "hyperparam_tune_best.yaml"
    existing: dict[str, Any] = {}
    if best_path.exists():
        with open(best_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    mp = dict(existing.get("model_params") or {})
    mp[algo] = best_params
    existing["model_params"] = mp
    existing["note"] = (
        "Validation 탐색 추천값. configs/default.yaml 의 model_params 에 "
        "수동 병합한 뒤 05→07→08→10 으로 Test 확정."
    )
    with open(best_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)

    print(f"[tune] 저장: {json_path.name}, {xlsx_path.name}, {best_path.name}")
    return json_path


def run_tuning(
    algorithms: list[str] | None = None,
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    cfg = load_config()
    tune_cfg = cfg.get("tune") or {}
    targets = [
        normalize_algo_id(a)
        for a in (algorithms or list(tune_cfg.get("algorithms") or ["random_forest_v1", "catboost_v1"]))
    ]
    results: dict[str, Any] = {}
    for algo in targets:
        results[algo] = tune_one_algorithm(algo, cfg, show_progress=show_progress)
    print("[tune] 완료 (Test 미사용 · 집계만 저장)")
    return results
