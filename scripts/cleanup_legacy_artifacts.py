"""레거시 파이프라인 산출물·운영 DB 일괄 삭제 (Run 격리 구현 전 정리용).

삭제 (기본):
  - {data_root}/interim/**
  - {data_root}/processed/**
  - {data_root}/algorithms/**
  - {data_root}/runs/**  (run_config·로그·Job·스냅샷·_*.json)
  - {data_root}/ops/**   (ops.sqlite 포함)
  - 프로젝트 outputs/reports/**  (Excel·PDF 등, 폴더는 유지)
    ※ outputs/reports/tuning/ (v2·v3 튜닝 결과) 는 기본 보존

보존 (기본):
  - {data_root}/raw/**
  - {data_root}/raw_inference/**
  - configs/local.yaml
  - outputs/reports/tuning/**  (하이퍼파라미터 튜닝 v2·v3 등)

Cursor Agent는 실행하지 마세요. 웹 서버를 종료한 뒤 사용자가 로컬에서 실행합니다.

  python scripts/cleanup_legacy_artifacts.py
  python scripts/cleanup_legacy_artifacts.py --yes
  python scripts/cleanup_legacy_artifacts.py --yes --also-raw   # raw 까지 삭제 (주의)
  python scripts/cleanup_legacy_artifacts.py --yes --also-tuning  # tuning/ 까지 삭제 (주의)
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.config import get_data_root, load_config  # noqa: E402


DATA_ROOT_TARGETS = (
    "interim",
    "processed",
    "algorithms",
    "runs",
    "ops",
)

REPO_REPORT_DIRS = (
    ROOT / "outputs" / "reports",
)

# 서비스 업데이트·Run 초기화 후에도 유지할 reports 하위 (튜닝 v2·v3 등)
REPORTS_PRESERVE_SUBDIRS = frozenset({"tuning"})


def _rm_tree(path: Path) -> bool:
    if not path.exists():
        return False
    if path.is_file() or path.is_symlink():
        path.unlink(missing_ok=True)
        return True
    shutil.rmtree(path, ignore_errors=False)
    return True



def _clear_reports_dir(
    reports_dir: Path,
    *,
    preserve_subdirs: frozenset[str] = REPORTS_PRESERVE_SUBDIRS,
) -> tuple[int, list[str]]:
    """outputs/reports 내용 정리. tuning/ 등 preserve_subdirs 는 유지."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    removed = 0
    kept: list[str] = []
    for child in list(reports_dir.iterdir()):
        if child.is_dir() and child.name in preserve_subdirs:
            kept.append(child.name)
            continue
        _rm_tree(child)
        removed += 1
    (reports_dir / "comparison").mkdir(parents=True, exist_ok=True)
    return removed, kept


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Delete legacy pipeline artifacts and ops DB (keep raw by default)."
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    parser.add_argument(
        "--also-raw",
        action="store_true",
        help="Also delete raw/ and raw_inference/ (irreversible)",
    )
    parser.add_argument(
        "--skip-reports",
        action="store_true",
        help="Do not clear project outputs/reports",
    )
    parser.add_argument(
        "--also-tuning",
        action="store_true",
        help="Also delete outputs/reports/tuning/ (hyperparam tune v2·v3 artifacts)",
    )
    parser.add_argument(
        "data_root",
        nargs="?",
        default=None,
        help="Override data_root (else configs/local.yaml)",
    )
    args = parser.parse_args()

    local = ROOT / "configs" / "local.yaml"
    if args.data_root:
        root = Path(args.data_root).expanduser().resolve()
        cfg = load_config()
        cfg["data_root"] = str(root)
    else:
        if not local.exists():
            print("[ERROR] configs/local.yaml missing.")
            return 1
        cfg = load_config()
        try:
            root = get_data_root(cfg)
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1

    targets = [root / name for name in DATA_ROOT_TARGETS]
    if args.also_raw:
        targets.extend([root / "raw", root / "raw_inference"])

    print("=== cleanup_legacy_artifacts ===")
    print(f"data_root = {root}")
    print()
    print("Will REMOVE (if present):")
    for t in targets:
        mark = "exists" if t.exists() else "missing"
        try:
            label = t.relative_to(root)
        except ValueError:
            label = t
        print(f"  - {label}  [{mark}]")
    if not args.skip_reports:
        for rd in REPO_REPORT_DIRS:
            if args.also_tuning:
                print(f"  - (repo) {rd.relative_to(ROOT)}/  [contents incl. tuning]")
            else:
                print(
                    f"  - (repo) {rd.relative_to(ROOT)}/  [contents except tuning/]"
                )
    print()
    print("Will KEEP:")
    if not args.also_raw:
        print("  - raw/")
        print("  - raw_inference/")
    print("  - configs/local.yaml")
    if not args.skip_reports and not args.also_tuning:
        print("  - outputs/reports/tuning/  (hyperparam tune v2·v3)")
    print()

    if not args.yes:
        ans = input("Type YES to proceed: ").strip()
        if ans != "YES":
            print("Aborted.")
            return 1

    removed = 0
    for t in targets:
        if not t.exists():
            print(f"  skip (missing): {t.name}")
            continue
        _rm_tree(t)
        removed += 1
        print(f"  removed: {t.name}/")

    if not args.skip_reports:
        preserve = frozenset() if args.also_tuning else REPORTS_PRESERVE_SUBDIRS
        for rd in REPO_REPORT_DIRS:
            n, kept = _clear_reports_dir(rd, preserve_subdirs=preserve)
            kept_msg = f", kept {', '.join(kept)}" if kept else ""
            print(f"  cleared: outputs/reports/ ({n} top-level entries{kept_msg}) + comparison/")

    # Recreate empty skeleton (shared only — Run outputs live under runs/{run_id}/)
    for name in ("ops", "runs"):
        (root / name).mkdir(parents=True, exist_ok=True)
    if not args.also_raw:
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "raw_inference").mkdir(parents=True, exist_ok=True)

    print()
    print(f"Done. removed_top_level={removed}")
    print("Next:")
    print("  1) (optional) python scripts/init_data_root.py")
    print("  2) RunWebNext.bat restart")
    print("  3) New Run ID → re-run pipeline from 01")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
