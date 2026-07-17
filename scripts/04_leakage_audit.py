"""
[로컬 전용] 타겟 누수(leakage) 점검 — 집계만 출력

권장 실행 시점: 03_preprocess.py 직후, 05_train.py 이전
(학습 전에 의심 Feature를 걸러 재학습 비용을 줄인다)

출력: outputs/reports/comparison/leakage_audit.xlsx
- 제외 컬럼이 Feature에 남았는지
- Feature별 단변량 ROC-AUC / PR-AUC (Train)
- 의심 임계값 초과 Feature 목록
- (행·PII·개별 ID 출력 없음)

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.preprocess import encode_target, time_split_masks  # noqa: E402
from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config, resolve_data_path, resolve_repo_path  # noqa: E402

# 단변량 AUC가 이 값 이상이면 "타겟과 과도하게 유사" 후보로 표시
SUSPECT_ROC_AUC = 0.90
SUSPECT_PR_AUC_RATIO = 20.0  # PR-AUC / base_rate 배수


def _safe_roc_auc(y: np.ndarray, score: np.ndarray) -> float | None:
    if len(np.unique(y)) < 2:
        return None
    if np.nanstd(score) == 0:
        return None
    try:
        return float(roc_auc_score(y, score))
    except ValueError:
        return None


def _safe_pr_auc(y: np.ndarray, score: np.ndarray) -> float | None:
    if len(np.unique(y)) < 2:
        return None
    try:
        return float(average_precision_score(y, score))
    except ValueError:
        return None


def _feature_score_series(s: pd.Series) -> np.ndarray:
    """범주/문자를 수치 점수로 변환 (Train 내 LabelEncoder)."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce").fillna(0.0).to_numpy(dtype=float)
    # 문자형: 빈도 순 인코딩이 아니라 단순 라벨 인코딩 + 결측
    x = s.astype(str).fillna("MISSING")
    enc = LabelEncoder()
    try:
        return enc.fit_transform(x).astype(float)
    except Exception:
        return np.zeros(len(s), dtype=float)


def main() -> None:
    print_banner()
    cfg = load_config()
    interim = resolve_data_path(cfg, "interim")
    processed = resolve_data_path(cfg, "processed")
    reports = resolve_repo_path(cfg, "reports_comparison")
    reports.mkdir(parents=True, exist_ok=True)
    encoding = cfg.get("encoding", "EUC-KR")

    labeled = interim / "labeled.csv"
    bundle_path = processed / "preprocess_bundle.joblib"
    masks_path = processed / "split_masks.joblib"
    for p in (labeled, bundle_path, masks_path):
        if not p.exists():
            raise FileNotFoundError(f"{p} 없음.")

    print("[leakage] labeled/전처리 번들 로드 (행 내용은 출력하지 않음)...")
    df = pd.read_csv(labeled, encoding=encoding, dtype=str, low_memory=False)
    bundle = joblib.load(bundle_path)
    masks = joblib.load(masks_path)
    train_m = masks["train_mask"]

    features: list[str] = list(bundle["features"])
    target_col = cfg.get("target_column", "TAET_YN")
    exclude = set(cfg.get("exclude_features", []))
    exclude.update(cfg.get("key_columns", []))
    exclude.add(target_col)
    label_sources = set(cfg.get("label_rule", {}).get("source_columns", []))

    # 1) 제외 정책 위반 여부
    forbidden_in_features = sorted(set(features) & (exclude | label_sources | {target_col}))
    checklist = [
        {
            "점검항목(check)": "TAET_YN이 Feature에 포함되지 않음",
            "결과(result)": "PASS" if target_col not in features else "FAIL",
        },
        {
            "점검항목(check)": "라벨소스 3종(ISDP/ISRC/PMBZ) Feature 미포함",
            "결과(result)": "PASS"
            if not (set(features) & label_sources)
            else f"FAIL: {sorted(set(features) & label_sources)}",
        },
        {
            "점검항목(check)": "exclude_features/key가 Feature에 없음",
            "결과(result)": "PASS" if not forbidden_in_features else f"FAIL: {forbidden_in_features}",
        },
        {
            "점검항목(check)": f"사용 Feature 수",
            "결과(result)": str(len(features)),
        },
    ]

    y = encode_target(df.loc[train_m, target_col], cfg.get("positive_label", "Y"))
    base_rate = float(y.mean()) if len(y) else 0.0
    X_train = df.loc[train_m, features]

    # 2) 단변량 예측력
    rows = []
    for col in features:
        score = _feature_score_series(X_train[col])
        # 결측이 많으면 반대로도 한번 (결측 자체가 신호일 수 있음) — 여기선 0 대치만
        roc = _safe_roc_auc(y, score)
        pr = _safe_pr_auc(y, score)
        # 방향이 반대면 1-AUC
        if roc is not None and roc < 0.5:
            roc_best = 1.0 - roc
            score_flip = -score
            pr = _safe_pr_auc(y, score_flip) or pr
        else:
            roc_best = roc

        pr_lift = (pr / base_rate) if (pr is not None and base_rate > 0) else None
        suspect = bool(
            (roc_best is not None and roc_best >= SUSPECT_ROC_AUC)
            or (pr_lift is not None and pr_lift >= SUSPECT_PR_AUC_RATIO)
        )
        rows.append(
            {
                "피처(feature)": col,
                "단변량_ROC_AUC(univariate_roc_auc)": roc_best,
                "단변량_PR_AUC(univariate_pr_auc)": pr,
                "PR대비양성비율배수(pr_over_base_rate)": pr_lift,
                "의심여부(suspect)": suspect,
            }
        )

    uni = pd.DataFrame(rows).sort_values(
        by="단변량_ROC_AUC(univariate_roc_auc)",
        ascending=False,
        na_position="last",
    )
    suspects = uni[uni["의심여부(suspect)"] == True]  # noqa: E712

    # 3) 라벨 소스와 타겟 일치도(참고: Feature 아님 — 정의 검증)
    label_agree = []
    for c in sorted(label_sources):
        if c not in df.columns:
            continue
        src = (
            df.loc[train_m, c]
            .astype(str)
            .str.strip()
            .str.upper()
            .eq("Y")
            .astype(int)
            .to_numpy()
        )
        agree = float((src == y).mean())
        # 소스가 양성이면 타겟도 양성인지 (any_of_y 정의상 필수)
        if src.sum() > 0:
            precision_as_rule = float(y[src == 1].mean())
        else:
            precision_as_rule = None
        label_agree.append(
            {
                "라벨소스(column)": c,
                "타겟일치율(agreement_with_target)": agree,
                "소스Y일때_타겟Y비율(precision_if_source_Y)": precision_as_rule,
                "소스양성건수(source_positive_count)": int(src.sum()),
                "비고(note)": "Feature 제외 대상(정의용). 여기 값이 1에 가까운 것은 정상.",
            }
        )

    # 4) 요약 판정
    n_suspect = int(suspects.shape[0])
    hard_fail = bool(forbidden_in_features)
    if hard_fail:
        verdict = "FAIL_제외컬럼_Feature잔존"
    elif n_suspect >= 3:
        verdict = "WARN_고의심피처_다수_수동검토필요"
    elif n_suspect >= 1:
        verdict = "WARN_고의심피처_존재_수동검토필요"
    else:
        verdict = "PASS_직접누수징후_약함_고생능은신호강할가능성"

    summary = pd.DataFrame(
        [
            {"항목(item)": "판정(verdict)", "값(value)": verdict},
            {"항목(item)": "Train양성비율(base_rate)", "값(value)": base_rate},
            {"항목(item)": "의심피처수(suspect_count)", "값(value)": n_suspect},
            {
                "항목(item)": "의심기준(roc_auc>=)",
                "값(value)": SUSPECT_ROC_AUC,
            },
            {
                "항목(item)": "의심기준(pr_auc/base_rate>=)",
                "값(value)": SUSPECT_PR_AUC_RATIO,
            },
            {
                "항목(item)": "해석가이드",
                "값(value)": (
                    "단변량 ROC-AUC가 0.9 이상이면 타겟과 거의 같이 움직이는 피처일 수 있음. "
                    "다만 여러 피처가 중정도(0.7~0.85)만으로도 앙상블 AUC 0.97대는 충분히 가능."
                ),
            },
        ]
    )

    out = reports / "leakage_audit.xlsx"
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="요약(summary)", index=False)
        pd.DataFrame(checklist).to_excel(writer, sheet_name="제외정책(checklist)", index=False)
        uni.to_excel(writer, sheet_name="단변량(univariate)", index=False)
        suspects.to_excel(writer, sheet_name="의심피처(suspects)", index=False)
        pd.DataFrame(label_agree).to_excel(writer, sheet_name="라벨정의검증(label_def)", index=False)
        pd.DataFrame({"피처목록(features)": features}).to_excel(
            writer, sheet_name="피처목록(feature_list)", index=False
        )

    # 콘솔: 집계만
    print(f"[leakage] 판정: {verdict}")
    print(f"[leakage] 의심 피처 수: {n_suspect}")
    if n_suspect:
        top = suspects.head(15)
        print("[leakage] 의심 피처 Top (이름·ROC만):")
        for _, r in top.iterrows():
            print(
                f"  - {r['피처(feature)']}: "
                f"ROC={r['단변량_ROC_AUC(univariate_roc_auc)']}"
            )
    print(f"[leakage] 저장: {out}")

    meta_path = reports / "leakage_audit_summary.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "verdict": verdict,
                "suspect_count": n_suspect,
                "forbidden_in_features": forbidden_in_features,
                "base_rate": base_rate,
                "suspect_features": suspects["피처(feature)"].head(30).tolist(),
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"[leakage] 요약 JSON: {meta_path}")


if __name__ == "__main__":
    main()
