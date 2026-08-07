"""
[로컬 전용] Test 타겟 포착 분포 (3케이스 · PK·엔티티 · 4×4)

선행: 07_evaluate.py, 08_update_ranking.py 권장

출력 (GitHub 금지):
→ {data_root}/algorithms/operations/ops_queue_test_pk.csv
→ {data_root}/algorithms/operations/ops_queue_test_pk.xlsx
→ {data_root}/algorithms/operations/ops_queue_test_entity.csv
→ {data_root}/algorithms/operations/ops_queue_test_entity.xlsx

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
from src.pipeline.run_config import pipeline_run_id, resolve_pipeline_run_id  # noqa: E402
from src.scoring.ops_capture import (  # noqa: E402
    CASE_AUX_REF,
    CASE_ID_COL,
    CASE_PRIMARY_AUX,
    CASE_PRIMARY_REF,
    OPS_PAIR_SPECS,
    OpsPairSpec,
    aggregate_entity_queue,
    build_ops_pair_queue,
    parse_entity_keys,
    summarize_matrix_for,
    write_capture_workbook,
)


def _load_scores(path: Path, encoding: str):
    if not path.exists():
        return None
    import pandas as pd

    return pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False)


def _score_df(cfg: dict, algo: str | None):
    if not algo:
        return None
    path = resolve_algo_score_csv(cfg, algo, "test")
    encoding = cfg.get("encoding", "EUC-KR")
    return _load_scores(path, encoding)


def _case_row_col_dfs(
    spec: OpsPairSpec,
    scores: dict[str, object],
    roles: dict[str, str | None],
) -> tuple[object | None, object | None, str | None]:
    primary = roles.get("primary")
    aux = roles.get("aux")
    reference = roles.get("reference")

    if spec.case_id == CASE_PRIMARY_AUX:
        return scores.get(primary), scores.get(aux), None
    if spec.case_id == CASE_PRIMARY_REF:
        if not reference:
            return None, None, "참조 모델(reference) 없음 — 08 순위 3위 또는 Test 점수 필요"
        ref_df = scores.get(reference)
        if ref_df is None:
            return None, None, f"참조 모델 Test 점수 없음: {reference}"
        return scores.get(primary), ref_df, None
    if spec.case_id == CASE_AUX_REF:
        if not reference:
            return None, None, "참조 모델(reference) 없음 — 08 순위 3위 또는 Test 점수 필요"
        ref_df = scores.get(reference)
        if ref_df is None:
            return None, None, f"참조 모델 Test 점수 없음: {reference}"
        return scores.get(aux), ref_df, None
    return None, None, "unknown case"


def main() -> None:
    print_banner()
    cfg = load_config()
    encoding = cfg.get("encoding", "EUC-KR")
    ops_cfg = dict(cfg.get("ops_queue", {}))
    keys = list(cfg.get("key_columns", []))
    entity_keys = parse_entity_keys(cfg)

    repo = OpsRepository(cfg)
    run_id = resolve_pipeline_run_id(cfg, repo=repo)
    roles = repo.get_roles(run_id)
    primary, aux, reference = (
        roles["primary"],
        roles["aux"],
        roles["reference"],
    )
    ops_cfg["primary_algo"] = primary
    ops_cfg["aux_algo"] = aux

    print(
        f"[ops] 타겟 포착 분포(Test) · 주={primary}, 보={aux}, 참={reference or '(없음)'}"
    )

    score_cache: dict[str, object] = {}
    for algo in {primary, aux, reference}:
        if algo and algo not in score_cache:
            df = _score_df(cfg, algo)
            if df is not None:
                print(f"[ops] 점수 로드: {algo}")
            score_cache[algo] = df

    pk_queues: list = []
    entity_queues: list = []
    pk_by_case: dict[str, object] = {}
    entity_by_case: dict[str, object] = {}

    import pandas as pd

    for spec in OPS_PAIR_SPECS:
        row_df, col_df, err = _case_row_col_dfs(spec, score_cache, roles)
        if err or row_df is None:
            print(f"[ops] {spec.title}: skip — {err or '행 모델 점수 없음'}")
            continue
        if col_df is None:
            print(f"[ops] {spec.title}: skip — 열 모델 점수 없음")
            continue

        pk_q = build_ops_pair_queue(row_df, col_df, keys, ops_cfg, spec)
        ent_q = aggregate_entity_queue(pk_q, entity_keys, ops_cfg, spec)
        pk_queues.append(pk_q)
        entity_queues.append(ent_q)
        pk_by_case[spec.case_id] = pk_q
        entity_by_case[spec.case_id] = ent_q

        print(f"[ops] {spec.title}: PK={len(pk_q):,}, entity={len(ent_q):,}")
        print(f"[ops]   4×4 PK 전체:\n{summarize_matrix_for(pk_q, spec).to_string()}")

    out_dir = resolve_data_path(cfg, "algorithms") / "operations"
    out_dir.mkdir(parents=True, exist_ok=True)

    pk_csv = out_dir / "ops_queue_test_pk.csv"
    pk_xlsx = out_dir / "ops_queue_test_pk.xlsx"
    ent_csv = out_dir / "ops_queue_test_entity.csv"
    ent_xlsx = out_dir / "ops_queue_test_entity.xlsx"

    if pk_queues:
        pd.concat(pk_queues, ignore_index=True).to_csv(
            pk_csv, index=False, encoding=encoding
        )
        write_capture_workbook(pk_by_case, entity_by_case, pk_xlsx, unit="pk")
    if entity_queues:
        pd.concat(entity_queues, ignore_index=True).to_csv(
            ent_csv, index=False, encoding=encoding
        )
        write_capture_workbook(pk_by_case, entity_by_case, ent_xlsx, unit="entity")

    repo.ensure_run(run_id, note="ops_capture")
    pk_n, ent_n = repo.replace_ops_capture(run_id, pk_queues, entity_queues)
    print(f"[ops] DB 적재: run_id={run_id}, pk_rows={pk_n:,}, entity_rows={ent_n:,}")
    print(f"[ops] 저장(로컬전용): {pk_csv}")
    print(f"[ops] 저장(로컬전용): {pk_xlsx}")
    print(f"[ops] 저장(로컬전용): {ent_csv}")
    print(f"[ops] 저장(로컬전용): {ent_xlsx}")
    print(f"[ops] data_root={get_data_root(cfg)}")


if __name__ == "__main__":
    main()
