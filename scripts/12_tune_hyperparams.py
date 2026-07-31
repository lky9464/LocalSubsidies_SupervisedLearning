"""
[로컬 전용] Validation 구간 하이퍼파라미터 소규모 탐색 (등록된 모든 family).

Test 구간은 사용하지 않습니다. 집계 리포트만 outputs/reports/tuning/{output_tag}/ 에 저장합니다.
선행: 03_preprocess (split.mode=group_random 권장) — tune은 train_mask 안에서만 Valid를
엔티티 단위 K-fold로 분리(nested_group_random)하므로, 03도 group_random이어야 Train/Test·
fit/Valid 양쪽 모두 사업·기관이 무중복이 됩니다.
설정: configs/tune.yaml (default.yaml 과 분리) · load_tune_config()
Run 격리(v0.5.2+): 03 산출물은 {data_root}/runs/{run_id}/ 아래에 있으므로 --run-id 를 지정하세요.
Cursor Agent는 실행하지 마세요.

사용:
  python scripts/12_tune_hyperparams.py --run-id 20260728_01
  python scripts/12_tune_hyperparams.py --run-id 20260728_01 --algo random_forest_v1
  python tune_batch/run_tune_batch.py --run-id 20260728_01
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import apply_tune_run_id, load_tune_config  # noqa: E402
from src.models.registry import normalize_algo_id  # noqa: E402
from src.models.tune import run_tuning  # noqa: E402


def main() -> None:
    print_banner()
    parser = argparse.ArgumentParser(description="Validation 하이퍼파라미터 탐색")
    parser.add_argument(
        "--algo",
        action="append",
        default=None,
        help="algo_id (예: random_forest_v1). 생략 시 configs/tune.yaml tune.algorithms",
    )
    parser.add_argument(
        "--run-id",
        default=None,
        help="03 산출물 Run ID. 생략 시 LSL_RUN_ID → configs/tune.yaml data_run_id",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="진행 로그 최소화",
    )
    args = parser.parse_args()

    tune_cfg = load_tune_config()
    run_id = apply_tune_run_id(tune_cfg, args.run_id)
    if run_id:
        print(f"[tune] run_id={run_id}")
    else:
        print(
            "[tune] run_id 미지정 — data_root 최상위 interim/processed 를 사용합니다. "
            "Run 산출물로 탐색하려면 --run-id 또는 configs/tune.yaml data_run_id 를 지정하세요."
        )

    algos = [normalize_algo_id(a) for a in args.algo] if args.algo else None
    run_tuning(algos, show_progress=not args.no_progress)


if __name__ == "__main__":
    main()
