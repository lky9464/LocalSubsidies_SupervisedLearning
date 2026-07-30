"""
[로컬 전용] 타겟 누수(leakage) 점검 — 집계만 출력

권장 실행 시점: 03_preprocess.py 직후, 05_train.py 이전
(학습 전에 의심 Feature를 걸러 재학습 비용을 줄인다)

출력: outputs/reports/comparison/leakage_audit.xlsx
- 제외 컬럼이 Feature에 남았는지
- Feature별 단변량 ROC-AUC / PR-AUC (Train)
- 의심 임계값 초과 Feature 목록
- 그룹(사업·기관) 단위 Train/Test 중복 비율 — 랜덤 분할 누수 진단
- (행·PII·개별 ID 출력 없음)

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.preprocessing import LabelEncoder

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features.group_audit import align_labeled_to_split_masks, group_overlap_stats, group_verdict  # noqa: E402
from src.features.preprocess import encode_target, time_split_masks  # noqa: E402
from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config, resolve_data_path, resolve_repo_path  # noqa: E402

# 단변량 AUC가 이 값 이상이면 "타겟과 과도하게 유사" 후보로 표시
SUSPECT_ROC_AUC = 0.90
SUSPECT_PR_AUC_RATIO = 20.0  # PR-AUC / base_rate 배수

# 그룹 중복 리포트 컬럼 라벨
GROUP_LABELS = {
    "group_key": "그룹키(group_key)",
    "n_rows": "전체행수(n_rows)",
    "n_rows_train": "Train행수(n_rows_train)",
    "n_rows_test": "Test행수(n_rows_test)",
    "n_entities": "엔티티수(n_entities)",
    "n_entities_train": "Train엔티티수(n_entities_train)",
    "n_entities_test": "Test엔티티수(n_entities_test)",
    "rows_per_entity_mean": "엔티티당평균행수(rows_per_entity_mean)",
    "rows_per_entity_max": "엔티티당최대행수(rows_per_entity_max)",
    "n_pos_rows": "양성행수(n_pos_rows)",
    "n_pos_rows_test": "Test양성행수(n_pos_rows_test)",
    "n_pos_entities": "양성엔티티수(n_pos_entities)",
    "n_pos_entities_train": "Train양성엔티티수(n_pos_entities_train)",
    "n_pos_entities_test": "Test양성엔티티수(n_pos_entities_test)",
    "pos_rows_per_pos_entity": "양성엔티티당양성행수(pos_rows_per_pos_entity)",
    "label_stickiness": "라벨고착성(label_stickiness)",
    "entity_overlap_ratio": "Test엔티티_Train중복비율(entity_overlap_ratio)",
    "pos_entity_seen_ratio": "Test양성엔티티_Train등장비율(pos_entity_seen_ratio)",
    "pos_entity_seen_positive_ratio": (
        "Test양성엔티티_Train에서이미양성비율(pos_entity_seen_positive_ratio)"
    ),
    "pos_row_seen_positive_ratio": "Test양성행_이미양성엔티티비율(pos_row_seen_positive_ratio)",
    "expected_overlap_under_random": "랜덤분할기대중복비율(expected_overlap_under_random)",
}


def _fmt_ratio(v: float | None) -> str:
    return "-" if v is None else f"{v * 100:.1f}%"


def _fmt_num(v: float | None) -> str:
    return "-" if v is None else f"{v:.1f}"


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
    from src.io.config import resolve_run_reports_dir

    reports = resolve_repo_path(cfg, "reports_comparison")
    reports.mkdir(parents=True, exist_ok=True)
    run_reports = resolve_run_reports_dir(cfg)
    if run_reports is not None:
        run_reports.mkdir(parents=True, exist_ok=True)
    labeled = interim / "labeled.csv"
    bundle_path = processed / "preprocess_bundle.joblib"
    masks_path = processed / "split_masks.joblib"
    for p in (labeled, bundle_path, masks_path):
        if not p.exists():
            raise FileNotFoundError(f"{p} 없음.")

    print("[leakage] labeled/전처리 번들 로드 (행 내용은 출력하지 않음)...")
    from src.io.encoding_util import read_csv_auto

    df, used = read_csv_auto(labeled, candidates=cfg.get("encoding_candidates"))
    print(f"[leakage] encoding={used}")
    bundle = joblib.load(bundle_path)
    masks = joblib.load(masks_path)
    df, train_m, test_m, pk_drop = align_labeled_to_split_masks(
        df, masks["train_mask"], masks["test_mask"]
    )
    if pk_drop["n_rows_dropped"]:
        checked = ", ".join(pk_drop["key_columns_checked"])
        print(
            f"[leakage] PK 결측 행 정렬: {pk_drop['n_rows_dropped']:,} / "
            f"{pk_drop['n_rows_before']:,} ({checked}) · "
            f"감사 대상 {pk_drop['n_rows_after']:,}행"
        )

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

    # 3-1) 그룹(엔티티) 중복 — 랜덤 분할에서 같은 사업의 다른 월이 Train/Test로 갈리는 문제
    audit_cfg = cfg.get("audit") or {}
    group_keys = [str(k) for k in (audit_cfg.get("group_keys") or [])]
    y_all = encode_target(df[target_col], cfg.get("positive_label", "Y"))
    group_stats: list[dict] = []
    group_notes: list[str] = []
    for key in group_keys:
        try:
            group_stats.append(group_overlap_stats(df, key, y_all, train_m, test_m))
        except (KeyError, ValueError) as exc:
            group_notes.append(f"{key}: 건너뜀 ({exc})")
    group_vd, group_worst = group_verdict(
        group_stats,
        warn_ratio=float(audit_cfg.get("group_warn_ratio", 0.5)),
        strong_warn_ratio=float(audit_cfg.get("group_strong_warn_ratio", 0.8)),
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
            {"항목(item)": "그룹중복판정(group_verdict)", "값(value)": group_vd},
            {
                "항목(item)": "최대_이미양성으로본비율(group_worst_ratio)",
                "값(value)": group_worst,
            },
            {
                "항목(item)": "그룹중복_해석가이드",
                "값(value)": (
                    "Test 양성 엔티티 중 Train에서 이미 양성으로 등장한 비율이 높으면, "
                    "지표가 '신규 대상 탐지'가 아니라 '기존 대상 재탐지' 성능을 재고 있을 수 있음. "
                    "랜덤분할기대중복비율과 비슷하면 원인은 행 단위 random 분할. "
                    "시간 분할(split.mode=time, 기간 겹침 금지) 또는 사업 단위 그룹 분할로 대조 권장."
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
        if group_stats:
            group_df = pd.DataFrame(
                [{GROUP_LABELS.get(k, k): v for k, v in s.items()} for s in group_stats]
            )
        else:
            group_df = pd.DataFrame({"비고(note)": group_notes or ["audit.group_keys 미설정"]})
        group_df.to_excel(writer, sheet_name="그룹중복(group_overlap)", index=False)
        pd.DataFrame({"피처목록(features)": features}).to_excel(
            writer, sheet_name="피처목록(feature_list)", index=False
        )
    if run_reports is not None:
        shutil.copy2(out, run_reports / "leakage_audit.xlsx")

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
    print(f"[leakage] 그룹중복 판정: {group_vd}")
    for s in group_stats:
        print(
            f"  - {s['group_key']}: 엔티티 {s['n_entities']:,} · "
            f"엔티티당 평균 {_fmt_num(s['rows_per_entity_mean'])}행 · "
            f"Test 양성 엔티티 {s['n_pos_entities_test']:,}"
        )
        print(
            f"      Train에 등장 {_fmt_ratio(s['pos_entity_seen_ratio'])} · "
            f"이미 양성으로 등장 {_fmt_ratio(s['pos_entity_seen_positive_ratio'])} "
            f"(랜덤 기대 {_fmt_ratio(s['expected_overlap_under_random'])}) · "
            f"라벨고착성 {_fmt_ratio(s['label_stickiness'])}"
        )
    for note in group_notes:
        print(f"  - {note}")
    print(f"[leakage] 저장: {out}")

    meta_payload = {
        "verdict": verdict,
        "suspect_count": n_suspect,
        "forbidden_in_features": forbidden_in_features,
        "base_rate": base_rate,
        "suspect_features": suspects["피처(feature)"].head(30).tolist(),
        "group_verdict": group_vd,
        "group_worst_seen_positive_ratio": group_worst,
        "group_overlap": group_stats,
        "group_notes": group_notes,
    }
    meta_path = reports / "leakage_audit_summary.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, ensure_ascii=False, indent=2)
    if run_reports is not None:
        with open(run_reports / "leakage_audit_summary.json", "w", encoding="utf-8") as f:
            json.dump(meta_payload, f, ensure_ascii=False, indent=2)
    print(f"[leakage] 요약 JSON: {meta_path}")

    # 하드 FAIL(제외 컬럼이 Feature에 잔존) 시 파이프라인 Job 중단 → UI에서 제외 후 03부터 재개
    if hard_fail:
        print("[leakage] FAIL — 제외 목록 반영 후 03 전처리부터 재실행하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
