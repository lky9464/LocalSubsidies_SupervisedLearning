"""
[로컬 전용] 알고리즘 학습 (일괄 또는 --algo 지정)

algo_id 형식: {family}_v{N} (예: catboost_v1, random_forest_v1)
선행: 03_preprocess.py, (권장) 04_leakage_audit.py PASS

예:
  python scripts/05_train.py
  python scripts/05_train.py --algo catboost_v1
  python scripts/05_train.py --algo random_forest_v1 --algo gradient_boosting_v1

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import load_config  # noqa: E402
from src.models.factory import ALGORITHM_NAMES  # noqa: E402
from src.models.registry import list_algo_ids, normalize_algo_id  # noqa: E402
from src.models.train_runner import run_training  # noqa: E402


def main() -> None:
    print_banner()
    cfg = load_config()
    choices = list_algo_ids(cfg) or list(ALGORITHM_NAMES)
    parser = argparse.ArgumentParser(description="지도학습 모델 학습 (일괄/선택)")
    parser.add_argument(
        "--algo",
        action="append",
        default=None,
        help=f"학습할 algo_id (여러 번 지정). 예: {choices[0]}. 생략 시 configs algorithms 전체",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="진행바/내부 verbose 비활성화",
    )
    args = parser.parse_args()
    algos = None
    if args.algo:
        algos = [normalize_algo_id(a) for a in args.algo]
    run_training(algos, show_progress=not args.no_progress)


if __name__ == "__main__":
    main()
