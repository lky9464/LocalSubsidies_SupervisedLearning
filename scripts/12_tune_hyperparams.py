"""
[로컬 전용] Validation 구간 하이퍼파라미터 소규모 탐색 (RF·CatBoost v*).

Test 구간은 사용하지 않습니다. 집계 리포트만 outputs/reports/comparison/ 에 저장합니다.
Cursor Agent는 실행하지 마세요.

사용:
  python scripts/12_tune_hyperparams.py
  python scripts/12_tune_hyperparams.py --algo random_forest_v1
  python scripts/12_tune_hyperparams.py --algo catboost_v1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.models.registry import normalize_algo_id  # noqa: E402
from src.models.tune import run_tuning  # noqa: E402


def main() -> None:
    print_banner()
    parser = argparse.ArgumentParser(description="Validation 하이퍼파라미터 탐색 (RF/CatBoost)")
    parser.add_argument(
        "--algo",
        action="append",
        default=None,
        help="algo_id (예: random_forest_v1, catboost_v1). 생략 시 configs tune.algorithms",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="진행 로그 최소화",
    )
    args = parser.parse_args()
    algos = [normalize_algo_id(a) for a in args.algo] if args.algo else None
    run_tuning(algos, show_progress=not args.no_progress)


if __name__ == "__main__":
    main()
