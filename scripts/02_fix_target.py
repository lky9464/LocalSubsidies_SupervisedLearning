"""
[로컬 전용] TAET_YN 수정 → data_root/interim/labeled.csv

기본 규칙(any_of_y): ISDP_RGSTR_YN / ISRC_DSCL_YN / PMBZ_CFMTN_YN 중 하나라도 Y.
실제 업무 규칙은 configs/default.yaml 의 label_rule을 사용자 기준으로 수정하세요.

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config, resolve_data_path  # noqa: E402
from src.io.label import apply_label_rule  # noqa: E402
from src.io.merge import save_interim_csv  # noqa: E402
from src.io.quality import print_summary, summarize_quality  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    interim = resolve_data_path(cfg, "interim")
    encoding = cfg.get("encoding", "EUC-KR")
    src = interim / "merged.csv"
    if not src.exists():
        raise FileNotFoundError(f"{src} 없음. 먼저 01_merge_raw.py를 실행하세요.")

    df = pd.read_csv(src, encoding=encoding, dtype=str, low_memory=False)
    df = apply_label_rule(
        df,
        rule=cfg.get("label_rule", {}),
        target_column=cfg.get("target_column", "TAET_YN"),
        positive_label=cfg.get("positive_label", "Y"),
        negative_label=cfg.get("negative_label", "N"),
    )
    summary = summarize_quality(df, target_column=cfg.get("target_column", "TAET_YN"))
    print_summary(summary)

    out = interim / "labeled.csv"
    save_interim_csv(df, out, encoding=encoding)
    print("[label] 완료. 규칙이 다르면 configs/default.yaml의 label_rule을 수정 후 재실행하세요.")


if __name__ == "__main__":
    main()
