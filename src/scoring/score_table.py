"""점수 산출 CSV용 부가 컬럼 (명칭·금액·기여도 TOP10 피처값)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pandas as pd

# 고정 부가 컬럼 (영문 소스 → 한글(영어) 헤더)
FIXED_SCORE_EXTRA_COLUMNS: list[tuple[str, str]] = [
    ("PFM_BIZ_NM", "수행사업명칭(PFM_BIZ_NM)"),
    ("INST_NM", "기관명(INST_NM)"),
    ("BIZCT_SBAT_AMT", "사업비보조금금액(BIZCT_SBAT_AMT)"),
    ("BIZCT_PYHWY_AMT", "사업비자부담금액(BIZCT_PYHWY_AMT)"),
]


def load_top_features_from_excel(
    xlsx_path: Path,
    *,
    top_n: int = 10,
) -> list[tuple[str, str]]:
    """
    feature_importance_top10.xlsx 에서 (영문피처, 한글명) 목록을 순위대로 로드.
    반환: [(FTEP_STF_NUM, 상근직원수), ...]
    """
    if not xlsx_path.exists():
        return []
    df = pd.read_excel(xlsx_path, sheet_name=0)
    feat_col = "피처명(feature)"
    ko_col = "피처명한글(feature_ko)"
    rank_col = "순위(rank)"
    if feat_col not in df.columns:
        return []
    if rank_col in df.columns:
        df = df.sort_values(rank_col)
    out: list[tuple[str, str]] = []
    for _, row in df.head(top_n).iterrows():
        en = str(row[feat_col]).strip()
        ko = str(row[ko_col]).strip() if ko_col in df.columns else ""
        if ko in ("", "nan", "None"):
            ko = en
        if en and en != "nan":
            out.append((en, ko))
    return out


def load_top_features_from_json(
    json_path: Path,
    *,
    top_n: int = 10,
) -> list[tuple[str, str]]:
    """algorithms/{algo}/feature_top10.json 에서 (영문, 한글) 목록 로드."""
    import json

    if not json_path.exists():
        return []
    with open(json_path, encoding="utf-8") as f:
        payload = json.load(f)
    items = payload.get("features", payload) if isinstance(payload, dict) else payload
    out: list[tuple[str, str]] = []
    for item in items[:top_n]:
        if isinstance(item, dict):
            en = str(item.get("feature", "")).strip()
            ko = str(item.get("feature_ko", "") or en).strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 1:
            en = str(item[0]).strip()
            ko = str(item[1]).strip() if len(item) >= 2 else en
        else:
            continue
        if ko in ("", "nan", "None"):
            ko = en
        if en and en != "nan":
            out.append((en, ko))
    return out


def save_top_features_json(
    json_path: Path,
    top_features: list[tuple[str, str]],
    *,
    algo: str,
) -> None:
    """evaluate/inference가 읽을 TOP10 JSON 저장."""
    import json

    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "algorithm": algo,
        "features": [
            {"rank": i + 1, "feature": en, "feature_ko": ko}
            for i, (en, ko) in enumerate(top_features)
        ],
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def resolve_top_features_for_algo(
    algo: str,
    cfg: dict[str, Any],
    *,
    top_n: int = 10,
) -> list[tuple[str, str]]:
    """알고리즘별 TOP10: algo JSON → reports xlsx → comparison 통합파일."""
    from src.io.config import (
        resolve_algo_dir,
        resolve_algo_report_dir,
        resolve_repo_path,
    )

    json_path = resolve_algo_dir(cfg, algo) / "feature_top10.json"
    tops = load_top_features_from_json(json_path, top_n=top_n)
    if tops:
        return tops

    primary = resolve_algo_report_dir(cfg, algo) / "feature_importance_top10.xlsx"
    tops = load_top_features_from_excel(primary, top_n=top_n)
    if tops:
        return tops

    all_path = resolve_repo_path(cfg, "reports_comparison") / "feature_importance_top10_all.xlsx"
    if all_path.exists():
        df = pd.read_excel(all_path, sheet_name=0)
        if "알고리즘(algorithm)" in df.columns:
            df = df[df["알고리즘(algorithm)"] == algo]
        feat_col = "피처명(feature)"
        ko_col = "피처명한글(feature_ko)"
        rank_col = "순위(rank)"
        if feat_col in df.columns:
            if rank_col in df.columns:
                df = df.sort_values(rank_col)
            out: list[tuple[str, str]] = []
            for _, row in df.head(top_n).iterrows():
                en = str(row[feat_col]).strip()
                ko = str(row[ko_col]).strip() if ko_col in df.columns else en
                if ko in ("", "nan", "None"):
                    ko = en
                if en and en != "nan":
                    out.append((en, ko))
            if out:
                return out
    return []


def top_feature_column_header(rank: int, feature_en: str, feature_ko: str) -> str:
    """기여도 TOP n 열 헤더: 기여도TOP01_상근직원수(FTEP_STF_NUM)"""
    return f"기여도TOP{rank:02d}_{feature_ko}({feature_en})"


FIXED_SCORE_EXTRA_HEADERS: list[str] = [h for _, h in FIXED_SCORE_EXTRA_COLUMNS]


def build_fixed_score_extra_frame(source_df: pd.DataFrame) -> pd.DataFrame:
    """명칭·금액 고정 4열."""
    out = pd.DataFrame(index=source_df.index)
    for src_col, header in FIXED_SCORE_EXTRA_COLUMNS:
        if src_col in source_df.columns:
            out[header] = source_df[src_col].astype(str).values
        else:
            out[header] = ""
    return out.reset_index(drop=True)


def build_top_feature_extra_frame(
    source_df: pd.DataFrame,
    top_features: list[tuple[str, str]],
    *,
    top_n: int = 10,
) -> pd.DataFrame:
    """기여도 TOP10 피처값 열 (항상 top_n개)."""
    out = pd.DataFrame(index=source_df.index)
    for rank in range(1, top_n + 1):
        if rank <= len(top_features):
            en, ko = top_features[rank - 1]
            header = top_feature_column_header(rank, en, ko)
            if en in source_df.columns:
                out[header] = source_df[en].astype(str).values
            else:
                out[header] = ""
        else:
            header = f"기여도TOP{rank:02d}_미산출(NA)"
            out[header] = ""
    return out.reset_index(drop=True)


def build_score_extra_frame(
    source_df: pd.DataFrame,
    top_features: list[tuple[str, str]],
    *,
    top_n: int = 10,
) -> pd.DataFrame:
    """고정 4열 + TOP10 (호환용; assemble는 분리 프레임을 권장)."""
    fixed = build_fixed_score_extra_frame(source_df)
    top = build_top_feature_extra_frame(source_df, top_features, top_n=top_n)
    return pd.concat([fixed, top], axis=1)


def assemble_score_table(
    key_df: pd.DataFrame,
    extra_df: pd.DataFrame,
    scores: Any,
    proba: Any,
    pred: Any,
    actual_label: Any | None = None,
    *,
    top_extra_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """
    컬럼 순서:
    키(CRTR_YM~) + 명칭/금액(~사업비자부담) → 위험도점수 → 양성확률
    → 예측라벨 → (선택)실제라벨 → 기여도TOP10…
    """
    out = key_df.reset_index(drop=True).copy()
    extra = extra_df.reset_index(drop=True)

    # 고정 부가 열 (extra에 섞여 있어도 헤더 기준으로만 앞쪽 배치)
    for header in FIXED_SCORE_EXTRA_HEADERS:
        if header in extra.columns:
            out[header] = extra[header].values

    out["위험도점수(risk_score)"] = scores
    out["양성확률(positive_probability)"] = proba
    out["예측라벨(predicted_label)"] = pred
    if actual_label is not None:
        out["실제라벨(actual_label)"] = actual_label

    # TOP10은 맨 뒤
    if top_extra_df is not None:
        top = top_extra_df.reset_index(drop=True)
        for c in top.columns:
            out[c] = top[c].values
    else:
        for c in extra.columns:
            if c.startswith("기여도TOP"):
                out[c] = extra[c].values

    return out


SCORE_COL = "위험도점수(risk_score)"


def top_pct_score_rows(
    score_df: pd.DataFrame,
    pct: float,
    *,
    score_col: str = SCORE_COL,
) -> pd.DataFrame:
    """위험도점수 상위 pct% 행 (ceil(n*pct/100), 점수 내림차순)."""
    n = len(score_df)
    if n == 0 or score_col not in score_df.columns:
        return score_df.iloc[0:0].copy()
    k = max(1, int(math.ceil(n * float(pct) / 100.0)))
    return (
        score_df.sort_values(score_col, ascending=False, kind="mergesort")
        .head(k)
        .reset_index(drop=True)
    )


def write_top_pct_score_excel(
    score_df: pd.DataFrame,
    out_path: Path,
    *,
    percents: tuple[float, ...] = (1.0, 5.0),
    score_col: str = SCORE_COL,
) -> Path:
    """
    상위 K% 점수 행을 시트별 1개 Excel로 저장.
    기본: 시트 '상위1%', '상위5%' → {algo}_test_scores_top.xlsx
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        for pct in percents:
            sheet = f"상위{int(pct) if float(pct).is_integer() else pct}%"
            # Excel 시트명 31자 제한
            sheet = sheet[:31]
            top_pct_score_rows(score_df, pct, score_col=score_col).to_excel(
                writer, sheet_name=sheet, index=False
            )
    return out_path
