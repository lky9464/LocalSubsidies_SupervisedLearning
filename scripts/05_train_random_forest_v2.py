"""[로컬 전용] RandomForest v2 학습 (Validation 튜닝 채택 하이퍼). Agent 실행 금지."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.models.train_runner import run_training  # noqa: E402


def main() -> None:
    print_banner()
    run_training(["random_forest_v2"], show_progress=True)


if __name__ == "__main__":
    main()
