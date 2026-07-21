"""raw CSV 다건 통합 (인코딩 자동 판별, 행 내용은 로그에 출력하지 않음)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.io.encoding_util import DEFAULT_ENCODING_CANDIDATES, read_csv_auto


def merge_raw_csvs(
    raw_dir: Path,
    encoding: str | None = None,
    pattern: str = "*.csv",
    candidates: list[str] | None = None,
    files: list[Path] | None = None,
) -> pd.DataFrame:
    """CSV를 세로 결합한다. files가 있으면 그 목록만, 없으면 raw_dir glob.

    파일명·건수·감지 인코딩만 요약한다(행 샘플 없음).
    """
    if files is not None:
        file_list = list(files)
        missing = [str(p) for p in file_list if not p.is_file()]
        if missing:
            raise FileNotFoundError(
                "선택한 CSV 파일이 없습니다: " + ", ".join(Path(m).name for m in missing)
            )
        if not file_list:
            raise FileNotFoundError("병합할 CSV 목록이 비어 있습니다.")
    else:
        file_list = sorted(raw_dir.glob(pattern))
        if not file_list:
            raise FileNotFoundError(f"CSV가 없습니다: {raw_dir} (pattern={pattern})")

    frames: list[pd.DataFrame] = []
    print(f"[merge] 파일 수: {len(file_list)}")
    cand = candidates or list(DEFAULT_ENCODING_CANDIDATES)
    for fp in file_list:
        df, used = read_csv_auto(fp, encoding=encoding, candidates=cand)
        print(
            f"[merge] 읽음: {fp.name} / 행수={len(df):,} / 컬럼수={df.shape[1]} "
            f"/ encoding={used}"
        )
        frames.append(df)

    merged = pd.concat(frames, axis=0, ignore_index=True)
    print(f"[merge] 통합 행수={len(merged):,} / 컬럼수={merged.shape[1]}")
    return merged


def save_interim_csv(df: pd.DataFrame, path: Path, encoding: str = "utf-8-sig") -> None:
    """중간 산출은 UTF-8(BOM)로 저장해 이후 단계·엑셀 호환을 맞춘다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding=encoding)
    print(f"[merge] 저장 완료: {path} (행수={len(df):,}, encoding={encoding})")


def check_keys(df: pd.DataFrame, key_columns: list[str]) -> dict[str, Any]:
    """키 중복·결측 집계만 반환 (행 샘플 없음)."""
    missing = {c: int(df[c].isna().sum()) for c in key_columns if c in df.columns}
    present = [c for c in key_columns if c in df.columns]
    dup = 0
    if present:
        dup = int(df.duplicated(subset=present).sum())
    return {"key_missing_counts": missing, "duplicate_key_rows": dup}
