"""
[로컬 전용] 라벨 미지 데이터(예: 2026) 위험도 점수 추론

선행: 05_train.py (저장된 모델·전처리), 06_feature_importance.py (TOP10 열)

입력: data_root/raw_inference/ 또는 --input-dir
출력: data_root/algorithms/{algo}/scores/inference_scores.csv
  - 키 + 명칭/금액 4열 + 기여도 TOP10 피처값 10열 + 점수

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.preprocess import transform_features  # noqa: E402
from src.io.banner import print_banner  # noqa: E402
from src.io.config import (  # noqa: E402
    ensure_algo_dirs,
    get_data_root,
    load_config,
    resolve_algo_dir,
    resolve_algo_scores_dir,
    resolve_data_path,
)
from src.io.merge import merge_raw_csvs  # noqa: E402
from src.scoring.risk_score import probability_to_score  # noqa: E402
from src.scoring.score_table import (  # noqa: E402
    assemble_score_table,
    build_score_extra_frame,
    resolve_top_features_for_algo,
)


def _predict_proba(model, X) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(X)
        if proba.ndim == 2 and proba.shape[1] >= 2:
            return proba[:, 1]
        return proba.ravel()
    pred = model.predict(X)
    return np.asarray(pred, dtype=float)


def main() -> None:
    print_banner()
    parser = argparse.ArgumentParser(description="라벨 미지 데이터 위험도 점수 추론")
    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="추론용 CSV 폴더 (기본: data_root/raw_inference)",
    )
    parser.add_argument(
        "--algo",
        type=str,
        default=None,
        help="특정 알고리즘만 (미지정 시 configs algorithms 전체)",
    )
    args = parser.parse_args()

    cfg = load_config()
    data_root = get_data_root(cfg)
    input_dir = Path(args.input_dir) if args.input_dir else data_root / "raw_inference"
    processed = resolve_data_path(cfg, "processed")
    encoding = cfg.get("encoding", "EUC-KR")
    scoring_cfg = cfg.get("scoring", {})
    top_n = int(cfg.get("feature_importance", {}).get("top_n", 10))
    algorithms = [args.algo] if args.algo else cfg.get("algorithms", [])
    ensure_algo_dirs(cfg, algorithms)

    if not input_dir.exists():
        raise FileNotFoundError(
            f"추론 입력 폴더 없음: {input_dir}. "
            "CSV를 두거나 --input-dir로 지정하세요."
        )

    df = merge_raw_csvs(input_dir, encoding=encoding)
    bundle = joblib.load(processed / "preprocess_bundle.joblib")
    features = bundle["features"]
    categorical = bundle["categorical"]
    numeric = bundle["numeric"]

    for c in features:
        if c not in df.columns:
            df[c] = np.nan
    X_raw = df[features]
    keys = [c for c in cfg.get("key_columns", []) if c in df.columns]
    key_df = df[keys].copy() if keys else pd.DataFrame(index=df.index)
    detail_df = df.reset_index(drop=True)
    key_df = key_df.reset_index(drop=True)

    for algo in algorithms:
        algo_dir = resolve_algo_dir(cfg, algo)
        model_path = algo_dir / "model.joblib"
        if not model_path.exists():
            print(f"[inference] 스킵 (모델 없음): {algo}")
            continue
        packed = joblib.load(model_path)
        model = packed["model"]
        pre = packed["preprocessor"]
        X, _ = transform_features(X_raw, pre, categorical, numeric)
        proba = _predict_proba(model, X)
        scores = probability_to_score(
            proba,
            min_score=scoring_cfg.get("min_score", 0),
            max_score=scoring_cfg.get("max_score", 1000),
        )
        pred = (proba >= 0.5).astype(int)

        top_feats = resolve_top_features_for_algo(algo, cfg, top_n=top_n)
        if not top_feats:
            print(
                f"[inference] 경고: {algo} Feature TOP10 없음. "
                "먼저 06_feature_importance.py를 실행하세요."
            )
        extra_df = build_score_extra_frame(detail_df, top_feats, top_n=top_n)
        # assemble이 고정열→점수/라벨→TOP10 순으로 재배치
        out = assemble_score_table(key_df, extra_df, scores, proba, pred)

        scores_dir = resolve_algo_scores_dir(cfg, algo)
        scores_dir.mkdir(parents=True, exist_ok=True)
        out_path = scores_dir / "inference_scores.csv"
        out.to_csv(out_path, index=False, encoding=encoding)
        print(
            f"[inference] 저장(로컬전용, 열수={out.shape[1]}): "
            f"{out_path} / 행수={len(out):,}"
        )


if __name__ == "__main__":
    main()
