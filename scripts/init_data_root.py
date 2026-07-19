"""Create data_root folder skeleton (raw / raw_inference / algo scores, etc.).

Usage:
  python scripts/init_data_root.py
  python scripts/init_data_root.py "D:/LocalSubsidies_ML_Data"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow `python scripts/init_data_root.py` from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.io.config import ensure_algo_dirs, get_data_root, load_config  # noqa: E402


BASE_DIRS = (
    "raw",
    "raw_inference",
    "interim",
    "processed",
    "ops",
    "algorithms/operations",
    "runs",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Init data_root folders")
    parser.add_argument(
        "data_root",
        nargs="?",
        default=None,
        help="Override data_root (else configs/local.yaml)",
    )
    args = parser.parse_args()

    if args.data_root:
        root = Path(args.data_root).expanduser().resolve()
        cfg = load_config()
        cfg["data_root"] = str(root)
    else:
        local = ROOT / "configs" / "local.yaml"
        if not local.exists():
            print("[ERROR] configs/local.yaml missing.")
            print("  Run SetupOffline.bat first, then edit data_root.")
            return 1
        cfg = load_config()
        try:
            root = get_data_root(cfg)
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1

    print(f"data_root = {root}")
    root.mkdir(parents=True, exist_ok=True)

    for rel in BASE_DIRS:
        p = root / rel
        created = not p.exists()
        p.mkdir(parents=True, exist_ok=True)
        mark = "+" if created else "="
        print(f"  {mark} {rel}")

    ensure_algo_dirs(cfg)
    print("  = algorithms/*/scores/test|inference (ensured)")

    print()
    print("Done.")
    print("  Training/eval CSV  -> raw\\")
    print("  Inference CSV      -> raw_inference\\")
    print("  Schema: TLS4902R_Layout.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
