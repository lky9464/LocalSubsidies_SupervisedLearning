"""CSV 인코딩 자동 판별 (EUC-KR 전제 없음)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

# 우선순위: BOM·UTF-8 → 한국어 레거시 → 기타
DEFAULT_ENCODING_CANDIDATES: tuple[str, ...] = (
    "utf-8-sig",
    "utf-8",
    "EUC-KR",
    "cp949",
    "latin-1",
)


def read_csv_auto(
    path: Path | str,
    *,
    encoding: str | None = None,
    candidates: Iterable[str] | None = None,
    **kwargs,
) -> tuple[pd.DataFrame, str]:
    """
    CSV를 읽어 (DataFrame, 사용된 인코딩) 반환.
    encoding이 주어지면 그것만 시도하고, 실패 시 candidates로 폴백.
    """
    path = Path(path)
    tried: list[str] = []
    order: list[str] = []
    if encoding:
        order.append(encoding)
    for c in candidates or DEFAULT_ENCODING_CANDIDATES:
        if c not in order:
            order.append(c)

    last_err: Exception | None = None
    for enc in order:
        tried.append(enc)
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, low_memory=False, **kwargs)
            return df, enc
        except UnicodeDecodeError as exc:
            last_err = exc
            continue
        except Exception as exc:  # noqa: BLE001
            # 인코딩 외 오류(파서 등)는 다른 인코딩으로도 재시도할 가치 있음
            last_err = exc
            continue

    raise ValueError(
        f"{path.name}: 지원 인코딩으로 읽기 실패 (시도={tried}). last={last_err}"
    )
