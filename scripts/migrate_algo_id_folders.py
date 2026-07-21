"""
[로컬 전용] algorithms/ 구 폴더명 → *_v1 rename.

예:
  python scripts/migrate_algo_id_folders.py --dry-run
  python scripts/migrate_algo_id_folders.py

Agent는 실행하지 마세요. 폴더명만 변경하며 파일 내용을 읽지 않습니다.
상세: docs/algo_id_migration.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import get_data_root, load_config, resolve_data_path  # noqa: E402

RENAMES: list[tuple[str, str]] = [
    ("catboost", "catboost_v1"),
    ("stacked_ensemble", "stacked_ensemble_v1"),
    ("easy_ensemble", "easy_ensemble_v1"),
    ("gradient_boosting", "gradient_boosting_v1"),
    ("random_forest", "random_forest_v1"),
]


def main() -> None:
    print_banner()
    parser = argparse.ArgumentParser(description="algorithms 폴더 *_v1 rename")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 rename 없이 예정만 출력",
    )
    args = parser.parse_args()

    cfg = load_config()
    root = get_data_root(cfg)
    algo_root = resolve_data_path(cfg, "algorithms")
    print(f"[migrate] data_root={root}")
    print(f"[migrate] algorithms={algo_root}")

    if not algo_root.is_dir():
        print(f"[migrate] 폴더 없음: {algo_root}")
        print("[migrate] data_root / InitDataRoot 확인 후 재실행하세요.")
        sys.exit(1)

    changed = 0
    for old_name, new_name in RENAMES:
        src = algo_root / old_name
        dst = algo_root / new_name
        if dst.exists():
            print(f"[migrate] SKIP (이미 있음): {new_name}/")
            continue
        if not src.exists():
            print(f"[migrate] SKIP (구 폴더 없음): {old_name}/")
            continue
        if args.dry_run:
            print(f"[migrate] DRY-RUN: {old_name}/ → {new_name}/")
            changed += 1
            continue
        src.rename(dst)
        print(f"[migrate] OK: {old_name}/ → {new_name}/")
        changed += 1

    # operations/ 은 유지
    ops = algo_root / "operations"
    if ops.is_dir():
        print("[migrate] operations/ 유지 (변경 없음)")

    if args.dry_run:
        print(f"[migrate] dry-run 완료 (예정 {changed}건). 실제 적용: --dry-run 없이 재실행")
    else:
        print(f"[migrate] 완료 (변경 {changed}건)")
        print("[migrate] 다음: docs/algo_id_migration.md §2~4 (DB·run_config·CLI 스모크)")


if __name__ == "__main__":
    main()
