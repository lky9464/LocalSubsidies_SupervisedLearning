"""
[로컬 전용] raw CSV 통합 → data_root/interim/merged.csv

LSL_RUN_ID 가 있으면 run_config.raw_files 만 병합한다.
없으면 data_root/raw 의 전체 *.csv (CLI 호환).

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import get_data_root, load_config, resolve_data_path  # noqa: E402
from src.io.merge import check_keys, merge_raw_csvs, save_interim_csv  # noqa: E402
from src.io.quality import print_summary, summarize_quality  # noqa: E402
from src.pipeline.run_config import load_run_config, resolve_run_raw_paths  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    raw_dir = resolve_data_path(cfg, "raw")
    interim_dir = resolve_data_path(cfg, "interim")
    preferred = cfg.get("encoding")
    candidates = cfg.get("encoding_candidates")

    run_id = (os.environ.get("LSL_RUN_ID") or "").strip()
    files = None
    if run_id:
        run_cfg = load_run_config(cfg, run_id)
        files = resolve_run_raw_paths(cfg, run_cfg, kind="train")
        if not files:
            raise FileNotFoundError(
                "run_config.raw_files 가 비어 있습니다. "
                "데이터 등록에서 학습 CSV를 선택한 뒤 학습을 다시 시작하세요."
            )
        print(f"[merge] Run {run_id}: 선택 파일 {len(files)}개")
        for p in files:
            print(f"[merge]  - {p.name}")

    df = merge_raw_csvs(
        raw_dir,
        encoding=preferred,
        candidates=list(candidates) if candidates else None,
        files=files,
    )
    key_info = check_keys(df, cfg.get("key_columns", []))
    print(f"[merge] 키점검: {key_info}")

    summary = summarize_quality(df, target_column=cfg.get("target_column", "TAET_YN"))
    print_summary(summary)

    out = interim_dir / "merged.csv"
    out_enc = cfg.get("interim_encoding", "utf-8-sig")
    save_interim_csv(df, out, encoding=out_enc)

    meta_path = interim_dir / "merged_quality.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        payload = {"key_info": key_info, "summary": summary}
        if run_id and files:
            root = get_data_root(cfg)
            payload["raw_files"] = [
                str(p.relative_to(root)).replace("\\", "/") for p in files
            ]
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"[merge] 품질 집계 JSON: {meta_path}")


if __name__ == "__main__":
    main()
