"""
[로컬 전용] Test 평가 + 위험도점수
→ {data_root}/algorithms/{algo}/eval_metrics.json
→ {data_root}/algorithms/{algo}/scores/test/{algo}_test_scores.csv
→ {data_root}/algorithms/{algo}/scores/test/{algo}_test_scores_top.xlsx
   (시트: 상위1%, 상위5% — 위험도점수 기준)

컬럼 순서:
  키·명칭/금액(~사업비자부담) → 위험도점수 → 양성확률 → 예측라벨 → 실제라벨 → 기여도TOP10

선행: 05_train.py, 06_feature_importance.py (TOP10 열)
공통 입력: interim/labeled.csv, processed/* (1벌 공유)
Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluate.metrics import (  # noqa: E402
    compute_classification_metrics,
    score_bin_target_rate,
    top_k_lift,
)
from src.features.preprocess import encode_target, transform_features  # noqa: E402
from src.io.banner import print_banner  # noqa: E402
from src.io.config import (  # noqa: E402
    ensure_algo_dirs,
    load_config,
    resolve_algo_dir,
    resolve_algo_scores_dir,
    resolve_data_path,
)
from src.scoring.risk_score import probability_to_score  # noqa: E402
from src.pipeline.run_config import resolve_pipeline_algorithms  # noqa: E402
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
    if hasattr(model, "decision_function"):
        from sklearn.preprocessing import MinMaxScaler

        d = model.decision_function(X).reshape(-1, 1)
        return MinMaxScaler().fit_transform(d).ravel()
    pred = model.predict(X)
    return np.asarray(pred, dtype=float)


def main() -> None:
    print_banner()
    cfg = load_config()
    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    algorithms = resolve_pipeline_algorithms(cfg)
    ensure_algo_dirs(cfg, algorithms)
    encoding = cfg.get("encoding", "EUC-KR")
    scoring_cfg = cfg.get("scoring", {})
    eval_cfg = cfg.get("evaluation", {})
    top_n = int(cfg.get("feature_importance", {}).get("top_n", 10))

    from src.io.encoding_util import read_csv_auto

    df, used = read_csv_auto(
        interim / "labeled.csv", candidates=cfg.get("encoding_candidates")
    )
    print(f"[evaluate] encoding={used}")
    bundle = joblib.load(processed / "preprocess_bundle.joblib")
    masks = joblib.load(processed / "split_masks.joblib")
    test_m = masks["test_mask"]
    features = bundle["features"]
    categorical = bundle["categorical"]
    numeric = bundle["numeric"]
    target = cfg.get("target_column", "TAET_YN")
    pos = cfg.get("positive_label", "Y")

    X_test_raw = df.loc[test_m, features]
    y_test = encode_target(df.loc[test_m, target], pos)
    keys = [c for c in cfg.get("key_columns", []) if c in df.columns]
    key_df = df.loc[test_m, keys].reset_index(drop=True)
    # 점수 CSV 부가 열용 원본 행 (명칭·금액·TOP10 피처값)
    detail_df = df.loc[test_m].reset_index(drop=True)

    all_metrics = {}
    all_lift = {}
    all_bins = {}
    algo_root = resolve_data_path(cfg, "algorithms")

    for algo in algorithms:
        algo_dir = resolve_algo_dir(cfg, algo)
        model_path = algo_dir / "model.joblib"
        if not model_path.exists():
            print(f"[evaluate] 스킵 (모델 없음): {algo}")
            continue
        packed = joblib.load(model_path)
        model = packed["model"]
        pre = packed["preprocessor"]
        X_te, _ = transform_features(X_test_raw, pre, categorical, numeric)
        proba = _predict_proba(model, X_te)
        pred = (proba >= 0.5).astype(int)
        scores = probability_to_score(
            proba,
            min_score=scoring_cfg.get("min_score", 0),
            max_score=scoring_cfg.get("max_score", 1000),
        )

        metrics = compute_classification_metrics(y_test, pred, proba)
        lift = top_k_lift(y_test, scores, eval_cfg.get("top_k_percents", [1, 5, 10]))
        bins = score_bin_target_rate(
            y_test,
            scores,
            n_bins=eval_cfg.get("score_bins", 10),
            min_cell_count=eval_cfg.get("min_cell_count", 5),
        )
        all_metrics[algo] = metrics
        all_lift[algo] = lift
        all_bins[algo] = bins

        top_feats = resolve_top_features_for_algo(algo, cfg, top_n=top_n)
        if not top_feats:
            print(
                f"[evaluate] 경고: {algo} Feature TOP10 없음. "
                "먼저 06_feature_importance.py를 실행하세요. TOP10 열은 빈 값으로 채웁니다."
            )

        else:
            print(
                f"[evaluate] {algo} TOP10 피처: "
                + ", ".join(f"{en}" for en, _ in top_feats)
            )

        fixed_df = build_fixed_score_extra_frame(detail_df)
        top_df = build_top_feature_extra_frame(detail_df, top_feats, top_n=top_n)
        out_scores = assemble_score_table(
            key_df,
            fixed_df,
            scores,
            proba,
            pred,
            actual_label=y_test,
            top_extra_df=top_df,
        )

        scores_dir = resolve_algo_scores_dir(cfg, algo, "test")
        scores_dir.mkdir(parents=True, exist_ok=True)
        score_path = scores_dir / f"{algo}_test_scores.csv"
        out_scores.to_csv(score_path, index=False, encoding=encoding)
        top_xlsx = scores_dir / f"{algo}_test_scores_top.xlsx"
        write_top_pct_score_excel(out_scores, top_xlsx, percents=(1.0, 5.0))
        n_top1 = max(1, int(np.ceil(len(out_scores) * 0.01)))
        n_top5 = max(1, int(np.ceil(len(out_scores) * 0.05)))
        print(
            f"[evaluate] {algo} 지표: "
            f"{ {k: metrics[k] for k in list(metrics)[:5]} }"
        )
        print(
            f"[evaluate] 행단위 점수 저장(로컬전용, 열수={out_scores.shape[1]}): "
            f"{score_path}"
        )
        print(
            f"[evaluate] 상위1%/5% Excel 저장 "
            f"(상위1%={n_top1:,}행, 상위5%={n_top5:,}행): {top_xlsx}"
        )

        with open(algo_dir / "eval_metrics.json", "w", encoding="utf-8") as f:
            json.dump(
                {
                    "metrics": metrics,
                    "lift": lift,
                    "score_bins": bins,
                    "score_extra_top_features": [
                        {"rank": i + 1, "feature": en, "feature_ko": ko}
                        for i, (en, ko) in enumerate(top_feats)
                    ],
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    summary_path = algo_root / "eval_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {"metrics": all_metrics, "lift": all_lift, "bins": all_bins},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[evaluate] 공통 비교 요약: {summary_path}")


if __name__ == "__main__":
    main()
