"""
[로컬 전용] Test 타겟 포착 분포 (주/보 상위% A~D · 4×4 · 우선순위 1~16)

Test 평가용: 주·보조가 실제 타겟을 어디에 모았는지 집계.
(추론 단계의「점검 우선순위표」와 동일 구간 규칙, 용도만 다름)

선행: 07_evaluate.py (주·보조 *_test_scores.csv), 08_update_ranking.py 권장

출력 (GitHub 금지):
→ {data_root}/algorithms/operations/ops_queue_test.csv
→ {data_root}/algorithms/operations/ops_queue_test.xlsx
   (시트: 전체, 우선순위요약, 4x4전체, 4x4실제양성, 주A, 주B, 주C)

Cursor Agent는 이 스크립트를 실행하지 마세요.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.banner import print_banner  # noqa: E402
from src.io.config import (  # noqa: E402
    get_data_root,
    load_config,
    resolve_algo_score_csv,
    resolve_data_path,
)
from src.ops_db.repository import OpsRepository  # noqa: E402
from src.pipeline.ranking import load_model_ranking  # noqa: E402
from src.pipeline.runner import new_run_id  # noqa: E402
from src.scoring.ops_queue import (  # noqa: E402
    GRADE_COL,
    PRIMARY_LABELS,
    PRIORITY_COL,
    build_ops_queue,
    summarize_matrix,
    write_ops_queue_excel,
)


def _resolve_primary_aux(cfg: dict) -> tuple[str, str, str | None]:
    """ranking.json → ops DB → default.yaml 순."""
    ops_cfg = cfg.get("ops_queue", {})
    default_p = ops_cfg.get("primary_algo", "random_forest")
    default_a = ops_cfg.get("aux_algo", "catboost")
    run_id = None

    rank_path = resolve_data_path(cfg, "algorithms") / "operations" / "model_ranking.json"
    ranking = load_model_ranking(rank_path)
    if ranking:
        primary = next((r["algo"] for r in ranking if r.get("role") == "primary"), None)
        aux = next((r["algo"] for r in ranking if r.get("role") == "aux"), None)
        if primary and aux:
            return primary, aux, run_id

    try:
        repo = OpsRepository(cfg)
        run_id = repo.get_latest_run_id()
        return (*repo.get_primary_aux(run_id), run_id)
    except Exception:  # noqa: BLE001
        return default_p, default_a, run_id


def _load_scores(path: Path, encoding: str):
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음. 먼저 07_evaluate.py를 실행하세요.")
    import pandas as pd

    return pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False)


def main() -> None:
    print_banner()
    cfg = load_config()
    encoding = cfg.get("encoding", "EUC-KR")
    ops_cfg = dict(cfg.get("ops_queue", {}))
    primary, aux, run_id = _resolve_primary_aux(cfg)
    ops_cfg["primary_algo"] = primary
    ops_cfg["aux_algo"] = aux
    keys = list(cfg.get("key_columns", []))
    print(f"[ops] 타겟 포착 분포(Test) · 주={primary}, 보조={aux}")

    primary_path = resolve_algo_score_csv(cfg, primary, "test")
    aux_path = resolve_algo_score_csv(cfg, aux, "test")

    print(f"[ops] 주 모델 점수 로드: {primary_path}")
    primary_df = _load_scores(primary_path, encoding)

    aux_df = None
    if aux_path.exists():
        print(f"[ops] 보조 모델 점수 로드: {aux_path}")
        aux_df = _load_scores(aux_path, encoding)
    else:
        print(f"[ops] 경고: {aux_path} 없음. 보조등급은 보D로 둡니다.")

    queue = build_ops_queue(primary_df, aux_df, keys, ops_cfg)

    out_dir = resolve_data_path(cfg, "algorithms") / "operations"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "ops_queue_test.csv"
    xlsx_path = out_dir / "ops_queue_test.xlsx"

    queue.to_csv(csv_path, index=False, encoding=encoding)
    write_ops_queue_excel(queue, xlsx_path, mode="test")

    repo = OpsRepository(cfg)
    if not run_id:
        run_id = repo.get_latest_run_id() or new_run_id()
    repo.ensure_run(run_id, note="ops_priority")
    n = repo.replace_ops_queue(run_id, queue)
    print(f"[ops] DB 적재: run_id={run_id}, rows={n:,}")

    counts = queue[GRADE_COL].value_counts().reindex(list(PRIMARY_LABELS)).fillna(0)
    print("[ops] 주등급별 건수:")
    for g, n_g in counts.items():
        print(f"  {g}: {int(n_g):,}")
    print("[ops] 4×4 전체:")
    print(summarize_matrix(queue).to_string())
    print("[ops] 4×4 실제 타겟=1:")
    print(summarize_matrix(queue, positive_only=True).to_string())
    top = queue.head(5)
    if PRIORITY_COL in top.columns:
        print(
            f"[ops] 최우선 미리보기(집계): 우선순위 "
            f"{int(top[PRIORITY_COL].iloc[0])} ~ "
            f"{int(top[PRIORITY_COL].iloc[-1])} 구간 상위 행"
        )
    print(f"[ops] 저장(로컬전용): {csv_path}")
    print(f"[ops] 저장(로컬전용): {xlsx_path}")
    print(f"[ops] data_root={get_data_root(cfg)}")


if __name__ == "__main__":
    main()
