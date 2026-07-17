"""EUC-KR raw CSV 다건 통합 (행 내용은 로그에 출력하지 않음)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def merge_raw_csvs(
    raw_dir: Path,
    encoding: str = "EUC-KR",
    pattern: str = "*.csv",
) -> pd.DataFrame:
    """raw_dir 내 CSV를 세로 결합한다. 파일명·건수만 요약한다."""
    files = sorted(raw_dir.glob(pattern))
    if not files:
        raise FileNotFoundError(f"CSV가 없습니다: {raw_dir} (pattern={pattern})")

    frames: list[pd.DataFrame] = []
    print(f"[merge] 파일 수: {len(files)}")
    for fp in files:
        df = pd.read_csv(fp, encoding=encoding, dtype=str, low_memory=False)
        print(f"[merge] 읽음: {fp.name} / 행수={len(df):,} / 컬럼수={df.shape[1]}")
        frames.append(df)

    merged = pd.concat(frames, axis=0, ignore_index=True)
    print(f"[merge] 통합 행수={len(merged):,} / 컬럼수={merged.shape[1]}")
    return merged


def save_interim_csv(df: pd.DataFrame, path: Path, encoding: str = "EUC-KR") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=encoding)
    print(f"[merge] 저장 완료: {path} (행수={len(df):,})")


def check_keys(df: pd.DataFrame, key_columns: list[str]) -> dict[str, Any]:
    """키 중복·결측 집계만 반환 (행 샘플 없음)."""
    missing = {c: int(df[c].isna().sum()) for c in key_columns if c in df.columns}
    present = [c for c in key_columns if c in df.columns]
    dup = 0
    if present:
        dup = int(df.duplicated(subset=present).sum())
    return {"key_missing_counts": missing, "duplicate_key_rows": dup}
