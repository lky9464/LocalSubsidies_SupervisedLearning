"""
[로컬 전용] Validation 구간 하이퍼파라미터 소규모 탐색 (등록된 모든 family).

Test 구간은 사용하지 않습니다. 집계 리포트만 outputs/reports/comparison/ 에 저장합니다.
선행: 03_preprocess (split.mode=random 권장) — tune은 train_mask 안에서만 Valid 분리(nested_random).
Run 격리(v0.5.2+): 03 산출물은 {data_root}/runs/{run_id}/ 아래에 있으므로 --run-id 를 지정하세요.
Cursor Agent는 실행하지 마세요.

사용:
  python scripts/12_tune_hyperparams.py --run-id 20260728_01
  python scripts/12_tune_hyperparams.py --run-id 20260728_01 --algo gradient_boosting_v1
  python scripts/12_tune_hyperparams.py --run-id 20260728_01 --algo stacked_ensemble_v1
  python scripts/12_tune_hyperparams.py --run-id 20260728_01 --algo easy_ensemble_v1
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.models.registry import normalize_algo_id  # noqa: E402
from src.models.tune import run_tuning  # noqa: E402


def main() -> None:
    print_banner()
    parser = argparse.ArgumentParser(description="Validation 하이퍼파라미터 탐색")
    parser.add_argument(
        "--algo",
        action="append",
        default=None,
        help="algo_id (예: gradient_boosting_v1). 생략 시 configs tune.algorithms",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="03 산출물이 있는 Run ID. 생략 시 환경변수 LSL_RUN_ID",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="진행 로그 최소화",
    )
    args = parser.parse_args()

    if args.run_id and args.run_id.strip():
        os.environ["LSL_RUN_ID"] = args.run_id.strip()
    run_id = (os.environ.get("LSL_RUN_ID") or "").strip()
    if run_id:
        print(f"[tune] run_id={run_id}")
    else:
        print(
            "[tune] run_id 미지정 — data_root 최상위 interim/processed 를 사용합니다. "
            "Run 산출물로 탐색하려면 --run-id 를 지정하세요."
        )

    algos = [normalize_algo_id(a) for a in args.algo] if args.algo else None
    run_tuning(algos, show_progress=not args.no_progress)


if __name__ == "__main__":
    main()
