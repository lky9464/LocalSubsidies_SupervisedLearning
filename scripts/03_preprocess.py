"""
[로컬 전용] 분할 + 전처리 객체/피처목록 저장 → data_root/processed/

분할: run_config.split.mode = time | random
메모리: OrdinalEncoder. Cursor Agent는 실행하지 마세요.
"""

from __future__ import annotations

import gc
import json
import os
import sys
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.preprocess import (  # noqa: E402
    build_feature_lists,
    encode_target,
    fit_preprocessor,
    random_split_masks,
    time_split_masks,
)
from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config, resolve_data_path  # noqa: E402
from src.io.encoding_util import read_csv_auto  # noqa: E402
from src.pipeline.run_config import load_run_config  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    run_id = os.environ.get("LSL_RUN_ID", "")
    run_cfg = load_run_config(cfg, run_id) if run_id else {}

    # run별 추가 제외 피처
    extra_ex = list(run_cfg.get("exclude_features_extra") or [])
    if extra_ex:
        cfg = dict(cfg)
        excl = list(cfg.get("exclude_features", []))
        for c in extra_ex:
            if c not in excl:
                excl.append(c)
        cfg["exclude_features"] = excl
        print(f"[preprocess] 추가 제외 피처 {len(extra_ex)}개 적용")

    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    processed.mkdir(parents=True, exist_ok=True)

    src = interim / "labeled.csv"
    if not src.exists():
        raise FileNotFoundError(f"{src} 없음. 먼저 02_fix_target.py를 실행하세요.")

    print("[preprocess] labeled.csv 로드 중...")
    df, used = read_csv_auto(src, candidates=cfg.get("encoding_candidates"))
    print(f"[preprocess] encoding={used}")

    split_cfg = run_cfg.get("split") or cfg.get("split", {})
    mode = split_cfg.get("mode", "random")
    if mode == "random":
        pool_start = split_cfg.get("pool_start") or split_cfg.get("train_start")
        pool_end = split_cfg.get("pool_end") or split_cfg.get("train_end")
        train_m, test_m = random_split_masks(
            df,
            test_size=float(split_cfg.get("test_size", 0.3)),
            random_state=int(split_cfg.get("random_state", cfg.get("random_seed", 42))),
            pool_start=str(pool_start) if pool_start else None,
            pool_end=str(pool_end) if pool_end else None,
        )
        pool_note = (
            f" pool={pool_start}~{pool_end}" if pool_start and pool_end else ""
        )
        print(
            f"[preprocess] 분할=random test_size={split_cfg.get('test_size', 0.3)}"
            f"{pool_note} "
            f"train={int(train_m.sum()):,} / test={int(test_m.sum()):,}"
        )
    else:
        train_m, test_m = time_split_masks(
            df,
            period_col="CRTR_YM",
            train_start=str(split_cfg.get("train_start", "202401")),
            train_end=str(split_cfg.get("train_end", "202506")),
            test_start=str(split_cfg.get("test_start", "202507")),
            test_end=str(split_cfg.get("test_end", "202512")),
        )
        print(
            f"[preprocess] 분할=time "
            f"train={int(train_m.sum()):,} / test={int(test_m.sum()):,}"
        )

    features, categorical, numeric = build_feature_lists(df, cfg)
    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")

    y_train = encode_target(df.loc[train_m, target], pos)
    y_test = encode_target(df.loc[test_m, target], pos)
    train_pos = float(y_train.mean()) if len(y_train) else None
    test_pos = float(y_test.mean()) if len(y_test) else None

    X_train = df.loc[train_m, features].copy()
    del df
    gc.collect()

    print("[preprocess] sklearn 전처리 fit (OrdinalEncoder)...")
    pre_sk, _ = fit_preprocessor(X_train, categorical, numeric, for_catboost=False)
    print("[preprocess] CatBoost 전처리 메타 생성...")
    pre_cb, _ = fit_preprocessor(X_train, categorical, numeric, for_catboost=True)

    del X_train
    gc.collect()

    joblib.dump(
        {
            "features": features,
            "categorical": categorical,
            "numeric": numeric,
            "preprocessor_sklearn": pre_sk,
            "preprocessor_catboost": pre_cb,
            "split": split_cfg,
            "random_seed": cfg.get("random_seed", 42),
            "sklearn_encoding": "ordinal",
        },
        processed / "preprocess_bundle.joblib",
    )

    meta = {
        "train_count": int(train_m.sum()),
        "test_count": int(test_m.sum()),
        "feature_count": len(features),
        "categorical_count": len(categorical),
        "numeric_count": len(numeric),
        "train_positive_rate": train_pos,
        "test_positive_rate": test_pos,
        "sklearn_encoding": "ordinal",
        "split_mode": mode,
        "features": features,
        "categorical": categorical,
        "numeric": numeric,
    }
    with open(processed / "preprocess_meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    joblib.dump(
        {"train_mask": train_m.to_numpy(), "test_mask": test_m.to_numpy()},
        processed / "split_masks.joblib",
    )
    print(f"[preprocess] 저장 완료: {processed}")


if __name__ == "__main__":
    main()
