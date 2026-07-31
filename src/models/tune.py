"""Validation 구간 하이퍼파라미터 소규모 탐색 (집계 지표만).

Test 구간은 사용하지 않는다. 기본 분할은 `nested_group_random` — Train 안에서
`PFM_BIZ_ID+INST_ID` 엔티티 단위 K-fold라 fit/valid가 같은 사업·기관을 공유하지
않는다. 행 단위 분할(`nested_random`)은 엔티티 암기로 Valid 지표가 부풀려진다.

Cursor Agent는 본 모듈을 data_root와 함께 실행하지 말 것.
"""

from __future__ import annotations

import gc
import hashlib
import itertools
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.evaluate.metrics import compute_classification_metrics, top_k_lift
from src.features.group_audit import align_labeled_to_split_masks, entity_codes
from src.features.preprocess import (
    encode_target,
    group_fold_masks_within_mask,
    group_split_masks_within_mask,
    transform_features,
)
from src.io.config import (
    get_active_run_id,
    load_tune_config,
    resolve_data_path,
    resolve_tune_output_dir,
)
from src.io.encoding_util import read_csv_auto
from src.models.factory import build_model, resolve_model_params
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


def fit_valid_masks_random_within_mask(
    parent_mask: np.ndarray | pd.Series,
    *,
    n_rows: int,
    valid_size: float = 0.2,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """부모 마스크(통상 Train) 안에서만 랜덤 fit/valid 분리. Test와 겹치지 않음."""
    from sklearn.model_selection import train_test_split

    parent = np.asarray(parent_mask, dtype=bool)
    if parent.shape[0] != n_rows:
        raise RuntimeError(
            f"마스크 길이 불일치: mask={parent.shape[0]} df={n_rows}"
        )
    idx = np.flatnonzero(parent)
    if len(idx) < 150:
        raise RuntimeError(
            f"튜닝용 Train 행 수 부족: {len(idx)}. 03_preprocess 분할을 확인하세요."
        )
    fit_idx, valid_idx = train_test_split(
        idx,
        test_size=float(valid_size),
        random_state=int(random_state),
        shuffle=True,
    )
    fit_m = np.zeros(n_rows, dtype=bool)
    valid_m = np.zeros(n_rows, dtype=bool)
    fit_m[fit_idx] = True
    valid_m[valid_idx] = True
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
    """CRTR_YM 풀 전체에서 랜덤 fit/valid (레거시·비권장: Test와 겹칠 수 있음)."""
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
    """tune.split_mode 에 따라 fit/valid 마스크와 설명 문자열 반환.

    - nested_random | random: 03의 train_mask 안에서만 Valid 분리 (Test 미사용, 권장)
    - pool_random: 기간 풀 전체 80/20 (레거시)
    - time: Train 내 기간 Valid
    """
    tune_cfg = cfg.get("tune") or {}
    split_cfg = cfg.get("split") or {}
    mode = str(tune_cfg.get("split_mode") or "nested_random").lower().strip()
    # 구 설정 random → nested_random 과 동일하게 취급 (Test 혼용 방지)
    if mode in ("nested_random", "random"):
        valid_size = float(tune_cfg.get("valid_size", 0.2))
        rs = int(tune_cfg.get("random_state", cfg.get("random_seed", 42)))
        fit_m, valid_m = fit_valid_masks_random_within_mask(
            train_mask,
            n_rows=len(df),
            valid_size=valid_size,
            random_state=rs,
        )
        n_train = int(np.asarray(train_mask, dtype=bool).sum())
        desc = (
            f"mode=nested_random within train_mask "
            f"train={n_train:,} valid_size={valid_size} seed={rs} (Test 미사용)"
        )
        return fit_m, valid_m, desc

    if mode == "pool_random":
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
            f"mode=pool_random pool={pool_start}~{pool_end} "
            f"valid_size={valid_size} seed={rs} (레거시·Test와 겹칠 수 있음)"
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


def resolve_tune_folds(
    df: pd.DataFrame,
    train_mask: np.ndarray | pd.Series,
    cfg: dict[str, Any],
) -> tuple[list[tuple[np.ndarray, np.ndarray]], str, dict[str, Any]]:
    """tune.split_mode → (fold 목록, 설명, 메타).

    nested_group_random: Train 안에서 `PFM_BIZ_ID+INST_ID` 엔티티 단위 K-fold.
    같은 엔티티가 fit과 valid에 동시에 들어가지 않는다. 그 외 모드는 fold 1개.
    """
    tune_cfg = cfg.get("tune") or {}
    split_cfg = cfg.get("split") or {}
    mode = str(tune_cfg.get("split_mode") or "nested_group_random").lower().strip()

    if mode not in ("nested_group_random", "group_random"):
        fit_m, valid_m, desc = resolve_tune_fit_valid(df, train_mask, cfg)
        return [(fit_m, valid_m)], desc, {"split_mode": mode, "group_key": None, "n_folds": 1}

    group_key = str(
        tune_cfg.get("group_key") or split_cfg.get("group_key") or "PFM_BIZ_ID+INST_ID"
    )
    rs = int(tune_cfg.get("random_state", cfg.get("random_seed", 42)))
    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")
    n_folds = int(tune_cfg.get("n_folds", 3))

    if n_folds >= 2:
        folds = group_fold_masks_within_mask(
            df,
            train_mask,
            group_key=group_key,
            target_col=target,
            positive_label=pos,
            n_folds=n_folds,
            random_state=rs,
        )
        desc = (
            f"mode=nested_group_random key={group_key} folds={n_folds} seed={rs} "
            "(엔티티 무중복 · Test 미사용)"
        )
    else:
        valid_size = float(tune_cfg.get("valid_size", 0.2))
        folds = [
            group_split_masks_within_mask(
                df,
                train_mask,
                group_key=group_key,
                target_col=target,
                positive_label=pos,
                valid_size=valid_size,
                random_state=rs,
            )
        ]
        desc = (
            f"mode=nested_group_random key={group_key} 단일분할 "
            f"valid_size={valid_size} seed={rs} (엔티티 무중복 · Test 미사용)"
        )
    meta = {"split_mode": "nested_group_random", "group_key": group_key, "n_folds": len(folds)}
    return folds, desc, meta


def audit_tune_folds(
    df: pd.DataFrame,
    folds: list[tuple[np.ndarray, np.ndarray]],
    *,
    group_key: str | None,
    target_col: str = "TAET_YN",
    positive_label: str = "Y",
) -> list[dict[str, Any]]:
    """fold별 행·양성·엔티티 집계. `entity_overlap`이 0이어야 무결 분할."""
    y_all = np.asarray(encode_target(df[target_col], positive_label))
    pos_rows = y_all == 1
    codes = entity_codes(df, group_key) if group_key else None

    out: list[dict[str, Any]] = []
    for i, (fit_m, valid_m) in enumerate(folds, start=1):
        info: dict[str, Any] = {
            "fold": i,
            "fit_rows": int(fit_m.sum()),
            "valid_rows": int(valid_m.sum()),
            "valid_pos_rows": int((valid_m & pos_rows).sum()),
        }
        if codes is not None:
            ent_fit = np.unique(codes[fit_m])
            ent_valid = np.unique(codes[valid_m])
            info["fit_entities"] = int(len(ent_fit))
            info["valid_entities"] = int(len(ent_valid))
            info["valid_pos_entities"] = int(len(np.unique(codes[valid_m & pos_rows])))
            info["entity_overlap"] = int(np.isin(ent_valid, ent_fit).sum())
        out.append(info)
    return out


def fold_positions_within_use(
    folds: list[tuple[np.ndarray, np.ndarray]],
    n_rows: int,
) -> tuple[np.ndarray, list[tuple[np.ndarray, np.ndarray]]]:
    """fold 전체가 쓰는 행 위치와, 그 부분집합 기준 fold별 fit/valid 위치 인덱스.

    원본 행을 fold 수만큼 복제하지 않기 위해 `use_pos` 한 벌만 잘라 두고
    fold마다 위치 인덱스로 슬라이싱한다.
    """
    use_m = np.zeros(n_rows, dtype=bool)
    for fit_m, valid_m in folds:
        use_m |= fit_m | valid_m
    use_pos = np.flatnonzero(use_m)

    lookup = np.full(n_rows, -1, dtype=np.int64)
    lookup[use_pos] = np.arange(len(use_pos))
    fold_idx = [
        (lookup[np.flatnonzero(fit_m)], lookup[np.flatnonzero(valid_m)])
        for fit_m, valid_m in folds
    ]
    return use_pos, fold_idx


def aggregate_fold_scores(fold_scores: list[dict[str, Any]]) -> dict[str, Any]:
    """fold별 지표를 평균. top1_lift는 fold 간 표준편차도 함께 남긴다."""
    if not fold_scores:
        return {}
    keys = list(fold_scores[0].keys())
    out: dict[str, Any] = {}
    for k in keys:
        vals = [s.get(k) for s in fold_scores if s.get(k) is not None]
        out[k] = float(np.mean(vals)) if vals else None
    t1 = [s.get("top1_lift") for s in fold_scores if s.get("top1_lift") is not None]
    out["top1_lift_std"] = float(np.std(t1)) if len(t1) > 1 else 0.0
    return out


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


def _preprocess_split_mode(processed: Path, bundle: dict[str, Any]) -> str | None:
    meta_path = processed / "preprocess_meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        mode = meta.get("split_mode")
        if mode:
            return str(mode).lower().strip()
    split_cfg = bundle.get("split") if isinstance(bundle.get("split"), dict) else {}
    mode = split_cfg.get("mode")
    return str(mode).lower().strip() if mode else None


def _validate_preprocess_for_tune(cfg: dict[str, Any], processed: Path, bundle: dict[str, Any]) -> None:
    required = cfg.get("require_preprocess_split_mode")
    if not required:
        return
    actual = _preprocess_split_mode(processed, bundle)
    want = str(required).lower().strip()
    if actual != want:
        raise RuntimeError(
            f"03 preprocess split.mode={actual!r} — tune.yaml require_preprocess_split_mode="
            f"{want!r} 와 불일치. 웹 Run 설정과 무관하게 03 산출물이 맞는지 확인하거나 "
            "CLI 로 03을 재실행하세요."
        )


def tune_one_algorithm(
    algo: str,
    cfg: dict[str, Any],
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    """단일 알고리즘 격자 탐색. 집계 결과만 반환·저장."""
    algo = normalize_algo_id(algo)
    family = family_of(algo)

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
    _validate_preprocess_for_tune(cfg, processed, bundle)
    df, train_m, _, pk_drop = align_labeled_to_split_masks(
        df, masks["train_mask"], masks["test_mask"]
    )
    if pk_drop["n_rows_dropped"]:
        print(
            f"[tune] PK 결측 행 정렬: {pk_drop['n_rows_dropped']:,} / "
            f"{pk_drop['n_rows_before']:,}"
        )

    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")

    folds, split_desc, split_meta = resolve_tune_folds(df, train_m, cfg)
    fold_audit = audit_tune_folds(
        df,
        folds,
        group_key=split_meta.get("group_key"),
        target_col=target,
        positive_label=pos,
    )
    leaky = [a for a in fold_audit if a.get("entity_overlap")]
    if leaky:
        raise RuntimeError(
            "튜닝 분할 무결성 위반: fit/valid가 동일 엔티티를 공유합니다 "
            f"(fold={[a['fold'] for a in leaky]}). tune.split_mode 설정을 확인하세요."
        )
    for a in fold_audit:
        if a["fit_rows"] < 100 or a["valid_rows"] < 50:
            raise RuntimeError(
                f"fold {a['fold']} 행 수 부족: fit={a['fit_rows']}, "
                f"valid={a['valid_rows']}. ({split_desc})"
            )

    print(f"[tune] {split_desc}")
    for a in fold_audit:
        extra = ""
        if "valid_pos_entities" in a:
            extra = (
                f" · valid 양성 엔티티 {a['valid_pos_entities']:,}"
                f" · 엔티티 교집합 {a['entity_overlap']}"
            )
        print(
            f"[tune]  fold {a['fold']}: fit={a['fit_rows']:,} valid={a['valid_rows']:,}"
            f" (양성 {a['valid_pos_rows']:,}행){extra}"
        )

    features = bundle["features"]
    categorical = bundle["categorical"]
    numeric = bundle["numeric"]
    seed = int(cfg.get("random_seed", 42))
    top_k = list((cfg.get("evaluation") or {}).get("top_k_percents") or [1, 5, 10])

    use_pos, fold_idx = fold_positions_within_use(folds, len(df))
    X_use_raw = df.iloc[use_pos][features].copy()
    y_use = np.asarray(encode_target(df.iloc[use_pos][target], pos))
    del df
    gc.collect()

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

    n_folds = len(fold_idx)
    print(
        f"[tune] 후보 수={len(combos)} × fold {n_folds} = 학습 {len(combos) * n_folds}회 "
        "(1번째 후보는 현재 model_params 기준선)"
    )
    rows: list[dict[str, Any]] = []

    for i, delta in enumerate(combos, start=1):
        params = {**base_params, **delta}
        if show_progress:
            print(f"[tune] [{i}/{len(combos)}] {algo} {delta or '(baseline)'}")
        t0 = time.perf_counter()
        fold_scores: list[dict[str, Any]] = []

        for k, (fit_pos, valid_pos) in enumerate(fold_idx, start=1):
            X_fit_raw = X_use_raw.iloc[fit_pos]
            X_val_raw = X_use_raw.iloc[valid_pos]
            y_fit = y_use[fit_pos]
            y_val = y_use[valid_pos]

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
            fold_scores.append(score_candidate(y_val, y_proba, top_k_percents=top_k))
            if show_progress and n_folds > 1:
                print(
                    f"[tune]   fold {k}/{n_folds} "
                    f"top1_lift={fold_scores[-1].get('top1_lift')}"
                )
            del model, X_tr, X_va, X_fit_raw, X_val_raw
            gc.collect()

        elapsed = round(time.perf_counter() - t0, 1)
        scored = aggregate_fold_scores(fold_scores)
        row = {
            "algorithm": algo,
            "trial": i,
            "params": params,
            "delta": delta,
            "elapsed_sec": elapsed,
            "n_folds": n_folds,
            "fold_top1_lift": [s.get("top1_lift") for s in fold_scores],
            **scored,
        }
        rows.append(row)
        if show_progress:
            print(
                f"[tune]   → {elapsed:,.1f}s "
                f"top1_lift(mean)={scored.get('top1_lift')} "
                f"±{scored.get('top1_lift_std')} pr_auc={scored.get('pr_auc')}"
            )

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
        "split_mode": split_meta.get("split_mode"),
        "group_key": split_meta.get("group_key"),
        "n_folds": n_folds,
        "fit_rows": int(np.mean([a["fit_rows"] for a in fold_audit])),
        "valid_rows": int(np.mean([a["valid_rows"] for a in fold_audit])),
        "folds": fold_audit,
        "baseline_precision": baseline_precision,
        "min_precision_ratio": min_prec_ratio,
        "best": best,
        "trials": ranked,
    }
    _save_tune_report(cfg, algo, out)
    return out


def _tune_config_digest() -> str:
    tune_path = Path(__file__).resolve().parents[2] / "configs" / "tune.yaml"
    if not tune_path.exists():
        return ""
    raw = tune_path.read_bytes()
    return hashlib.sha256(raw).hexdigest()[:16]


def _write_tune_manifest(cfg: dict[str, Any], *, algo: str | None = None) -> None:
    out_dir = resolve_tune_output_dir(cfg)
    manifest_path = out_dir / "tune_manifest.yaml"
    existing: dict[str, Any] = {}
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    tune_cfg = cfg.get("tune") or {}
    completed = list(existing.get("algorithms_completed") or [])
    if algo and algo not in completed:
        completed.append(algo)
    payload = {
        "output_tag": cfg.get("output_tag"),
        "run_id": get_active_run_id(),
        "split_mode": tune_cfg.get("split_mode"),
        "n_folds": tune_cfg.get("n_folds"),
        "group_key": tune_cfg.get("group_key") or (cfg.get("split") or {}).get("group_key"),
        "algorithms_target": tune_cfg.get("algorithms"),
        "algorithms_completed": completed,
        "tune_config_digest": _tune_config_digest(),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)


def _save_tune_report(cfg: dict[str, Any], algo: str, result: dict[str, Any]) -> Path:
    out_dir = resolve_tune_output_dir(cfg)
    json_path = out_dir / f"hyperparam_tune_{algo}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)

    flat_rows = []
    for t in result.get("trials") or []:
        flat = {
            "algorithm": t.get("algorithm"),
            "trial": t.get("trial"),
            "precision_guard_pass": t.get("precision_guard_pass"),
            "elapsed_sec": t.get("elapsed_sec"),
            "n_folds": t.get("n_folds"),
            "pr_auc": t.get("pr_auc"),
            "roc_auc": t.get("roc_auc"),
            "precision": t.get("precision"),
            "recall": t.get("recall"),
            "f1": t.get("f1"),
            "top1_lift": t.get("top1_lift"),
            "top1_lift_std": t.get("top1_lift_std"),
            "top5_lift": t.get("top5_lift"),
            "top1_recall": t.get("top1_recall"),
            "top5_recall": t.get("top5_recall"),
            "params_json": json.dumps(t.get("params") or {}, ensure_ascii=False),
        }
        flat_rows.append(flat)
    xlsx_path = out_dir / f"hyperparam_tune_{algo}.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        pd.DataFrame(flat_rows).to_excel(writer, sheet_name="후보(trials)", index=False)
        pd.DataFrame(result.get("folds") or []).to_excel(
            writer, sheet_name="분할무결성(folds)", index=False
        )

    # best yaml 조각 (수동 병합용)
    best = result.get("best") or {}
    best_params = (best.get("params") or {}) if best else {}
    best_path = out_dir / "hyperparam_tune_best.yaml"
    existing: dict[str, Any] = {}
    if best_path.exists():
        with open(best_path, encoding="utf-8") as f:
            existing = yaml.safe_load(f) or {}
    mp = dict(existing.get("model_params") or {})
    mp[algo] = best_params
    existing["model_params"] = mp
    tag = cfg.get("output_tag") or "v1"
    existing["output_tag"] = tag
    existing["note"] = (
        f"Validation 탐색 추천값 (tuning/{tag}/). configs/default.yaml model_params 에 "
        f"새 algo_id(예: {{family}}_{tag})로 등록한 뒤 05→07→08→10 Test 확정. "
        "기존 버전 수치는 덮어쓰지 말 것."
    )
    with open(best_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(existing, f, allow_unicode=True, sort_keys=False)

    _write_tune_manifest(cfg, algo=algo)
    rel = out_dir.relative_to(Path(__file__).resolve().parents[2])
    print(f"[tune] 저장: {rel / json_path.name}, {rel / xlsx_path.name}, {rel / best_path.name}")
    return json_path


def run_tuning(
    algorithms: list[str] | None = None,
    *,
    show_progress: bool = True,
) -> dict[str, Any]:
    cfg = load_tune_config()
    tune_cfg = cfg.get("tune") or {}
    targets = [
        normalize_algo_id(a)
        for a in (
            algorithms
            or list(
                tune_cfg.get("algorithms")
                or [
                    "random_forest_v1",
                    "catboost_v1",
                    "gradient_boosting_v1",
                    "stacked_ensemble_v1",
                    "easy_ensemble_v1",
                ]
            )
        )
    ]
    results: dict[str, Any] = {}
    for algo in targets:
        results[algo] = tune_one_algorithm(algo, cfg, show_progress=show_progress)
    print("[tune] 완료 (Test 미사용 · 집계만 저장)")
    return results
