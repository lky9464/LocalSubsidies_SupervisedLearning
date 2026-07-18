"""
[로컬 전용] 라벨 미지 데이터(예: 2026) 위험도 점수 추론

선행: 05_train.py (저장된 모델·전처리), 06_feature_importance.py (TOP10 열)

입력: data_root/raw_inference/ 또는 --input-dir
출력 (Test 점수와 동일 양식·명명 규칙, scores/inference/ 하위):
  {data_root}/algorithms/{algo}/scores/inference/{algo}_inference_scores.csv
  {data_root}/algorithms/{algo}/scores/inference/{algo}_inference_scores_top.xlsx
  - 키 + 명칭/금액 → 위험도점수 → 양성확률 → 예측라벨 → 실제라벨(비움) → 기여도 TOP10

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
    build_fixed_score_extra_frame,
    build_top_feature_extra_frame,
    resolve_top_features_for_algo,
    write_top_pct_score_excel,
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
        action="append",
        default=None,
        help="특정 알고리즘 (여러 번 지정 가능). 미지정 시 configs algorithms 전체",
    )
    args = parser.parse_args()

    cfg = load_config()
    data_root = get_data_root(cfg)
    input_dir = Path(args.input_dir) if args.input_dir else data_root / "raw_inference"
    processed = resolve_data_path(cfg, "processed")
    encoding = cfg.get("encoding", "EUC-KR")
    scoring_cfg = cfg.get("scoring", {})
    top_n = int(cfg.get("feature_importance", {}).get("top_n", 10))
    algorithms = list(args.algo) if args.algo else list(cfg.get("algorithms", []))
    ensure_algo_dirs(cfg, algorithms)

    if not input_dir.exists():
        raise FileNotFoundError(
            f"추론 입력 폴더 없음: {input_dir}. "
            "CSV를 두거나 --input-dir로 지정하세요."
        )

    df = merge_raw_csvs(
        input_dir,
        encoding=encoding,
        candidates=list(cfg.get("encoding_candidates") or []),
    )
    # 학습 raw와 동일 레이아웃이어도 타겟·타겟수정 컬럼은 추론에서 무시
    ignore_cols = list(
        (cfg.get("inference") or {}).get("ignore_columns")
        or [
            cfg.get("target_column", "TAET_YN"),
            *list((cfg.get("label_rule") or {}).get("source_columns") or []),
        ]
    )
    dropped = [c for c in ignore_cols if c in df.columns]
    if dropped:
        df = df.drop(columns=dropped)
        print(f"[inference] 무시 컬럼 drop: {', '.join(dropped)}")

    bundle = joblib.load(processed / "preprocess_bundle.joblib")
    features = list(bundle["features"])
    categorical = list(bundle["categorical"])
    numeric = list(bundle["numeric"])
    ignore_set = set(ignore_cols)
    features = [c for c in features if c not in ignore_set]
    categorical = [c for c in categorical if c not in ignore_set]
    numeric = [c for c in numeric if c not in ignore_set]

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
                "먼저 06_feature_importance.py를 실행하세요. TOP10 열은 빈 값으로 채웁니다."
            )
        else:
            print(
                f"[inference] {algo} TOP10 피처: "
                + ", ".join(en for en, _ in top_feats)
            )

        # Test(07)와 동일 조립: 고정4열 → 점수/확률/예측/실제 → TOP10
        # 추론은 실제 라벨이 없으므로 스키마 유지를 위해 빈 값
        actual_empty = np.full(len(detail_df), np.nan)
        fixed_df = build_fixed_score_extra_frame(detail_df)
        top_df = build_top_feature_extra_frame(detail_df, top_feats, top_n=top_n)
        out_scores = assemble_score_table(
            key_df,
            fixed_df,
            scores,
            proba,
            pred,
            actual_label=actual_empty,
            top_extra_df=top_df,
        )

        scores_dir = resolve_algo_scores_dir(cfg, algo, "inference")
        scores_dir.mkdir(parents=True, exist_ok=True)
        score_path = scores_dir / f"{algo}_inference_scores.csv"
        out_scores.to_csv(score_path, index=False, encoding=encoding)
        top_xlsx = scores_dir / f"{algo}_inference_scores_top.xlsx"
        write_top_pct_score_excel(out_scores, top_xlsx, percents=(1.0, 5.0))
        n_top1 = max(1, int(np.ceil(len(out_scores) * 0.01)))
        n_top5 = max(1, int(np.ceil(len(out_scores) * 0.05)))
        print(
            f"[inference] 행단위 점수 저장(로컬전용, 열수={out_scores.shape[1]}): "
            f"{score_path} / 행수={len(out_scores):,}"
        )
        print(
            f"[inference] 상위1%/5% Excel 저장 "
            f"(상위1%≈{n_top1:,}행, 상위5%≈{n_top5:,}행): {top_xlsx}"
        )


if __name__ == "__main__":
    main()
