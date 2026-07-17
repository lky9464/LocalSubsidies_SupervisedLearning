"""
[로컬 전용] 알고리즘별 Feature 중요도 TOP10 + 기여도 + 사유

선행: 05_train.py (모델 학습 완료 후)
후행: 07_evaluate.py (test_scores TOP10 열에 사용)

출력:
- {data_root}/algorithms/{algo}/feature_top10.json  (evaluate/inference용)
- outputs/reports/{algo}/feature_importance_top10.xlsx
- outputs/reports/comparison/feature_importance_top10_all.xlsx

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""


from __future__ import annotations

import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.evaluate.feature_importance import (  # noqa: E402
    compute_top_features,
    load_column_comments,
    strip_transformer_prefix,
)
from src.features.preprocess import encode_target, transform_features  # noqa: E402
from src.io.banner import print_banner  # noqa: E402
from src.io.config import (  # noqa: E402
    PROJECT_ROOT,
    ensure_algo_dirs,
    load_config,
    resolve_algo_dir,
    resolve_algo_report_dir,
    resolve_data_path,
    resolve_repo_path,
)
from src.scoring.score_table import save_top_features_json  # noqa: E402



def _sklearn_feature_names(preprocessor, fallback: list[str]) -> list[str]:
    try:
        names = list(preprocessor.get_feature_names_out())
        return [strip_transformer_prefix(n) for n in names]
    except Exception:
        return list(fallback)


def main() -> None:
    print_banner()
    cfg = load_config()
    algorithms = cfg.get("algorithms", [])
    ensure_algo_dirs(cfg, algorithms)
    encoding = cfg.get("encoding", "EUC-KR")
    top_n = int(cfg.get("feature_importance", {}).get("top_n", 10))

    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    comparison = resolve_repo_path(cfg, "reports_comparison")
    comparison.mkdir(parents=True, exist_ok=True)

    layout_path = PROJECT_ROOT / "TLS4902R_Layout.csv"
    comments = load_column_comments(layout_path)

    print("[fi] 데이터·전처리 로드...")
    df = pd.read_csv(interim / "labeled.csv", encoding=encoding, dtype=str, low_memory=False)
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
    del df

    all_rows: list[pd.DataFrame] = []

    for algo in algorithms:
        algo_dir = resolve_algo_dir(cfg, algo)
        model_path = algo_dir / "model.joblib"
        if not model_path.exists():
            print(f"[fi] 스킵 (모델 없음): {algo}")
            continue

        print(f"[fi] === {algo} Feature 중요도 산출 ===")
        packed = joblib.load(model_path)
        model = packed["model"]
        pre = packed["preprocessor"]

        if algo == "catboost":
            X_te, cols = transform_features(X_test_raw, pre, categorical, numeric)
            feat_names = list(cols) if cols else list(numeric) + list(categorical)
        else:
            X_te, _ = transform_features(X_test_raw, pre, categorical, numeric)
            feat_names = _sklearn_feature_names(pre, list(numeric) + list(categorical))

        top_df = compute_top_features(
            algo,
            model,
            feat_names,
            X_te,
            y_test,
            comments,
            top_n=top_n,
            permutation_sample_size=int(
                cfg.get("feature_importance", {}).get("permutation_sample_size", 8000)
            ),
            permutation_repeats=int(
                cfg.get("feature_importance", {}).get("permutation_repeats", 2)
            ),
        )
        all_rows.append(top_df)

        # evaluate/inference가 읽을 머신용 TOP10 (06→07 순차 실행용)
        top_pairs = [
            (str(r["피처명(feature)"]), str(r["피처명한글(feature_ko)"]))
            for _, r in top_df.iterrows()
        ]
        json_path = algo_dir / "feature_top10.json"
        save_top_features_json(json_path, top_pairs, algo=algo)
        print(f"[fi] 저장: {json_path}")

        out_dir = resolve_algo_report_dir(cfg, algo)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "feature_importance_top10.xlsx"
        with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
            top_df.to_excel(writer, sheet_name="TOP10", index=False)
            pd.DataFrame(
                [
                    {
                        "안내": (
                            "기여도비중은 해당 알고리즘 내에서 합이 1이 되도록 정규화한 값입니다. "
                            "사유는 변수 의미(레이아웃)와 중요도 측정 방법을 함께 설명합니다. "
                            "행단위 raw 데이터는 포함되지 않습니다."
                        )
                    }
                ]
            ).to_excel(writer, sheet_name="안내(guide)", index=False)
        print(f"[fi] 저장: {out_path}")
        # 콘솔에는 순위·피처명·비중만
        for _, r in top_df.iterrows():
            print(
                f"  #{int(r['순위(rank)'])} {r['피처명(feature)']} "
                f"({r['피처명한글(feature_ko)']}) "
                f"비중={r['기여도비중(importance_share)']:.2%}"
            )

    if not all_rows:
        print("[fi] 결과 없음")
        return

    combined = pd.concat(all_rows, ignore_index=True)
    all_path = comparison / "feature_importance_top10_all.xlsx"
    with pd.ExcelWriter(all_path, engine="openpyxl") as writer:
        combined.to_excel(writer, sheet_name="전체TOP10(all)", index=False)
        for algo, g in combined.groupby("알고리즘(algorithm)"):
            sheet = f"{algo}"[:31]
            g.to_excel(writer, sheet_name=sheet, index=False)
    print(f"[fi] 공통 비교 저장: {all_path}")


if __name__ == "__main__":
    main()
