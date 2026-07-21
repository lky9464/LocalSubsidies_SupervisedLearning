"""공통 학습 러너: 일괄/개별 스크립트가 공유."""

from __future__ import annotations

import gc
import json
import os
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from src.features.preprocess import encode_target, transform_features
from src.io.config import (
    ensure_algo_dirs,
    load_config,
    resolve_algo_dir,
    resolve_data_path,
)
from src.models.factory import (
    ALGORITHM_NAMES,
    build_model,
    get_model_progress_info,
    resolve_model_params,
)
from src.models.progress import CatBoostTqdmCallback, algo_progress, progress_backend_name
from src.models.registry import family_of, list_algo_ids, normalize_algo_id
from src.pipeline.run_config import load_run_config


def _merge_run_model_params(cfg: dict[str, Any]) -> dict[str, Any]:
    """LSL_RUN_ID 가 있으면 run_config.model_params 를 cfg.model_params 에 병합."""
    run_id = os.environ.get("LSL_RUN_ID", "").strip()
    if not run_id:
        return cfg
    run_cfg = load_run_config(cfg, run_id)
    run_mp = run_cfg.get("model_params") or {}
    if not run_mp:
        return cfg
    out = dict(cfg)
    base_mp = dict(out.get("model_params") or {})
    for algo, params in run_mp.items():
        if isinstance(params, dict):
            base_mp[algo] = {**(base_mp.get(algo) or {}), **params}
        else:
            base_mp[algo] = params
    out["model_params"] = base_mp
    print(f"[train] run_config model_params 병합 (run_id={run_id})")
    return out


def load_train_context(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """학습용 공통 데이터·전처리 번들을 로드한다 (집계 로그만)."""
    cfg = _merge_run_model_params(cfg or load_config())
    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    labeled = interim / "labeled.csv"
    bundle_path = processed / "preprocess_bundle.joblib"
    masks_path = processed / "split_masks.joblib"
    for p in (labeled, bundle_path, masks_path):
        if not p.exists():
            raise FileNotFoundError(f"{p} 없음. 01~03(전처리) 단계를 먼저 실행하세요.")

    print("[train] labeled.csv 로드...")
    from src.io.encoding_util import read_csv_auto

    df, used = read_csv_auto(labeled, candidates=cfg.get("encoding_candidates"))
    print(f"[train] encoding={used}")
    bundle = joblib.load(bundle_path)
    masks = joblib.load(masks_path)
    train_m = masks["train_mask"]
    features = bundle["features"]
    categorical = bundle["categorical"]
    numeric = bundle["numeric"]
    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")

    X_train_raw = df.loc[train_m, features].copy()
    y_train = encode_target(df.loc[train_m, target], pos)
    del df
    gc.collect()

    print(f"[train] train_rows={int(np.asarray(train_m).sum()):,} / features={len(features)}")
    return {
        "cfg": cfg,
        "bundle": bundle,
        "train_m": train_m,
        "X_train_raw": X_train_raw,
        "y_train": y_train,
        "features": features,
        "categorical": categorical,
        "numeric": numeric,
    }


def train_one_algorithm(
    algo: str,
    ctx: dict[str, Any],
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    """단일 알고리즘 학습·저장. 메타(집계)만 반환."""
    cfg = ctx["cfg"]
    algo = normalize_algo_id(algo)
    known = set(list_algo_ids(cfg)) | set(ALGORITHM_NAMES)
    if algo not in known:
        raise ValueError(f"알 수 없는 알고리즘: {algo}. 지원={sorted(known)}")
    family = family_of(algo)

    bundle = ctx["bundle"]
    X_train_raw = ctx["X_train_raw"]
    y_train = ctx["y_train"]
    train_m = ctx["train_m"]
    categorical = ctx["categorical"]
    numeric = ctx["numeric"]
    seed = cfg.get("random_seed", 42)

    ensure_algo_dirs(cfg, [algo])
    out_dir = resolve_algo_dir(cfg, algo)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[train] === {algo} 학습 시작 ===")
    model_params = resolve_model_params(cfg, algo)
    info = get_model_progress_info(algo, cfg=cfg, params=model_params)

    if family == "catboost":
        pre = bundle["preprocessor_catboost"]
        print("[train] 피처 변환(CatBoost)...")
        X_tr, cols = transform_features(X_train_raw, pre, categorical, numeric)
        model = build_model(
            algo,
            random_seed=seed,
            cat_features=categorical,
            cfg=cfg,
            params=model_params,
        )
        callbacks = []
        cb = None
        if show_progress:
            cb = CatBoostTqdmCallback(info.get("iterations", 400), desc=f"{algo}")
            callbacks.append(cb)
        try:
            model.fit(
                X_tr,
                y_train,
                cat_features=categorical,
                callbacks=callbacks if callbacks else None,
                verbose=False,
            )
        finally:
            if cb is not None:
                cb.close()
        joblib.dump(
            {
                "model": model,
                "preprocessor": pre,
                "feature_cols": cols,
                "algo": algo,
                "family": family,
            },
            out_dir / "model.joblib",
        )
        del X_tr, model
    else:
        pre = bundle["preprocessor_sklearn"]
        print("[train] 피처 변환(sklearn Ordinal)...")
        X_tr, _ = transform_features(X_train_raw, pre, categorical, numeric)
        model = build_model(
            algo,
            random_seed=seed,
            show_progress=show_progress,
            cfg=cfg,
            params=model_params,
        )
        print(f"[train] {algo} fit 중... (내부 verbose/진행 메시지 가능)")
        model.fit(X_tr, y_train)
        joblib.dump(
            {"model": model, "preprocessor": pre, "algo": algo, "family": family},
            out_dir / "model.joblib",
        )
        del X_tr, model

    meta = {
        "algorithm": algo,
        "family": family,
        "train_rows": int(np.asarray(train_m).sum()),
        "train_positive_rate": float(np.asarray(y_train).mean()),
        "random_seed": seed,
        "model_params": model_params,
    }
    with open(out_dir / "train_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print(f"[train] 저장: {out_dir / 'model.joblib'}")
    gc.collect()
    return meta


def merge_train_summary(cfg: dict[str, Any], new_meta: dict[str, Any]) -> None:
    """algorithms/train_summary.json 에 알고리즘 결과 병합."""
    algo_root = resolve_data_path(cfg, "algorithms")
    algo_root.mkdir(parents=True, exist_ok=True)
    path = algo_root / "train_summary.json"
    summary: dict[str, Any] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            summary = json.load(f) or {}
    summary[new_meta["algorithm"]] = new_meta
    with open(path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)


def run_training(
    algorithms: list[str] | None = None,
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    """일괄 또는 지정 알고리즘 학습."""
    cfg = load_config()
    all_algos = list_algo_ids(cfg)
    targets = [normalize_algo_id(a) for a in (algorithms or all_algos)]
    for a in targets:
        if a not in set(all_algos) | set(ALGORITHM_NAMES):
            raise ValueError(f"알 수 없는 알고리즘: {a}. 지원={all_algos}")

    ensure_algo_dirs(cfg, targets)
    print(f"[train] 진행 표시: {progress_backend_name()}")
    ctx = load_train_context(cfg)
    results: dict[str, Any] = {}

    iterator = algo_progress(list(targets), desc="학습(알고리즘)") if show_progress else targets
    for algo in iterator:
        if show_progress and hasattr(iterator, "set_postfix_str"):
            iterator.set_postfix_str(algo)
        meta = train_one_algorithm(algo, ctx, show_progress=show_progress)
        results[algo] = meta
        merge_train_summary(cfg, meta)

    print("[train] 요청 알고리즘 학습 완료")
    return results
