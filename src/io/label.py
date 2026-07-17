"""TAET_YN 수정 규칙 적용."""

from __future__ import annotations

from typing import Any

import pandas as pd


def apply_label_rule(
    df: pd.DataFrame,
    rule: dict[str, Any],
    target_column: str = "TAET_YN",
    positive_label: str = "Y",
    negative_label: str = "N",
) -> pd.DataFrame:
    """
    label_rule에 따라 타겟을 재작성한다.

    mode:
      - any_of_y: source_columns 중 하나라도 Y(대소문자 무시)이면 양성
      - all_of_y: 모두 Y이면 양성
      - custom_map: 추후 확장용 (현재 미구현)
    """
    out = df.copy()
    mode = rule.get("mode", "any_of_y")
    cols = rule.get("source_columns", [])
    missing = [c for c in cols if c not in out.columns]
    if missing:
        raise KeyError(f"라벨 규칙 소스 컬럼 없음: {missing}")

    def _is_y(series: pd.Series) -> pd.Series:
        return series.astype(str).str.strip().str.upper().eq("Y")

    flags = [_is_y(out[c]) for c in cols]
    if mode == "any_of_y":
        positive = flags[0]
        for f in flags[1:]:
            positive = positive | f
    elif mode == "all_of_y":
        positive = flags[0]
        for f in flags[1:]:
            positive = positive & f
    else:
        raise ValueError(
            f"지원하지 않는 label_rule.mode={mode}. "
            "사용자 규칙이 확정되면 configs/default.yaml을 수정하세요."
        )

    out[target_column] = positive.map({True: positive_label, False: negative_label})
    pos_n = int(positive.sum())
    print(
        f"[label] mode={mode} / 양성={pos_n:,} "
        f"({pos_n / max(len(out), 1):.4%}) / 전체={len(out):,}"
    )
    return out
