"""
[로컬 전용] raw CSV 8개 통합 → data_root/interim/merged.csv

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config, resolve_data_path  # noqa: E402
from src.io.merge import check_keys, merge_raw_csvs, save_interim_csv  # noqa: E402
from src.io.quality import print_summary, summarize_quality  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    raw_dir = resolve_data_path(cfg, "raw")
    interim_dir = resolve_data_path(cfg, "interim")
    # encoding: 우선 시도값(실패 시 utf-8/EUC-KR/cp949 등 자동 폴백)
    preferred = cfg.get("encoding")
    candidates = cfg.get("encoding_candidates")
    df = merge_raw_csvs(
        raw_dir,
        encoding=preferred,
        candidates=list(candidates) if candidates else None,
    )
    key_info = check_keys(df, cfg.get("key_columns", []))
    print(f"[merge] 키점검: {key_info}")

    summary = summarize_quality(df, target_column=cfg.get("target_column", "TAET_YN"))
    print_summary(summary)

    out = interim_dir / "merged.csv"
    # 중간파일은 UTF-8로 통일 (이후 단계는 read_csv_auto 권장)
    out_enc = cfg.get("interim_encoding", "utf-8-sig")
    save_interim_csv(df, out, encoding=out_enc)

    meta_path = interim_dir / "merged_quality.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"key_info": key_info, "summary": summary}, f, ensure_ascii=False, indent=2)
    print(f"[merge] 품질 집계 JSON: {meta_path}")


if __name__ == "__main__":
    main()
