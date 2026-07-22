"""
[로컬 전용] eval_summary.json → model_ranking.json + 운영 DB

선행: 07_evaluate.py
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
from src.ops_db.repository import OpsRepository  # noqa: E402
from src.pipeline.ranking import build_model_ranking, save_model_ranking  # noqa: E402
from src.pipeline.run_config import (  # noqa: E402
    resolve_pipeline_algorithms,
    resolve_pipeline_run_id,
)


def main() -> None:
    print_banner()
    cfg = load_config()
    algo_root = resolve_data_path(cfg, "algorithms")
    summary_path = algo_root / "eval_summary.json"
    if not summary_path.exists():
        raise FileNotFoundError(f"{summary_path} 없음. 먼저 07_evaluate.py 실행.")

    with open(summary_path, encoding="utf-8") as f:
        summary = json.load(f)

    algorithms = resolve_pipeline_algorithms(cfg)
    ranking = build_model_ranking(summary, algorithms=algorithms)
    out = algo_root / "operations" / "model_ranking.json"
    save_model_ranking(ranking, out)

    repo = OpsRepository(cfg)
    run_id = resolve_pipeline_run_id(cfg, repo=repo)
    repo.ensure_run(run_id, note="ranking")
    repo.save_ranking(run_id, ranking)

    print(f"[ranking] 저장: {out}")
    print(f"[ranking] DB run_id={run_id}")
    for r in ranking:
        print(
            f"  #{r['rank']} {r['algo']} role={r['role']} "
            f"PR-AUC={r.get('pr_auc')} top1_lift={r.get('top1_lift')}"
        )


if __name__ == "__main__":
    main()
