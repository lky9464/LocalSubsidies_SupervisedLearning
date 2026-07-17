"""
[로컬 전용] 시계열 분할 + 전처리 객체/피처목록 저장 → data_root/processed/

메모리: One-Hot 미사용(Ordinal). 대행수 대비 16GB RAM 환경 대응.
Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import gc
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.preprocess import (  # noqa: E402
    build_feature_lists,
    encode_target,
    fit_preprocessor,
    time_split_masks,
)
from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config, resolve_data_path  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    processed.mkdir(parents=True, exist_ok=True)
    encoding = cfg.get("encoding", "EUC-KR")

    src = interim / "labeled.csv"
    if not src.exists():
        raise FileNotFoundError(f"{src} 없음. 먼저 02_fix_target.py를 실행하세요.")

    print("[preprocess] labeled.csv 로드 중...")
    df = pd.read_csv(src, encoding=encoding, dtype=str, low_memory=False)
    split = cfg["split"]
    train_m, test_m = time_split_masks(
        df,
        period_col="CRTR_YM",
        train_start=split["train_start"],
        train_end=split["train_end"],
        test_start=split["test_start"],
        test_end=split["test_end"],
    )
    print(f"[preprocess] train={int(train_m.sum()):,} / test={int(test_m.sum()):,}")

    features, categorical, numeric = build_feature_lists(df, cfg)
    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")

    y_train = encode_target(df.loc[train_m, target], pos)
    y_test = encode_target(df.loc[test_m, target], pos)
    train_pos = float(y_train.mean()) if len(y_train) else None
    test_pos = float(y_test.mean()) if len(y_test) else None

    # Train 피처만 복사 후 원본 df 해제 → 피크 메모리 감소
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
            "split": split,
            "random_seed": cfg.get("random_seed", 42),
            "sklearn_encoding": "ordinal",  # 메모리 절약 모드
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
    print(
        f"[preprocess] train_positive_rate={train_pos:.6f} / "
        f"test_positive_rate={test_pos:.6f}"
        if train_pos is not None and test_pos is not None
        else "[preprocess] 완료"
    )


if __name__ == "__main__":
    main()
