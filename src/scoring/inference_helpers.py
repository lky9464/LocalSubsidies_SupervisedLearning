"""추론 결과 로드·집계·Excel 내보내기 (웹 UI 공용)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.io.config import (
    resolve_algo_score_csv,
    resolve_algo_score_top_xlsx,
)
from src.models.registry import list_algo_ids
from src.ops_db.repository import OpsRepository
from src.pipeline.run_config import load_run_config
from src.scoring.ops_queue import (
    build_ops_queue,
)
from src.scoring.score_table import SCORE_COL


def inference_score_path(
    cfg: dict[str, Any], algo: str, *, run_id: str | None = None
) -> Path:
    """scores/inference/{algo}_inference_scores.csv (Run 격리 경로)."""
    return resolve_algo_score_csv(cfg, algo, "inference", run_id=run_id)


def inference_top_xlsx_path(
    cfg: dict[str, Any], algo: str, *, run_id: str | None = None
) -> Path:
    return resolve_algo_score_top_xlsx(cfg, algo, "inference", run_id=run_id)


def _order_algos_by_ranking(cfg: dict[str, Any], run_id: str, algos: list[str]) -> list[str]:
    if len(algos) <= 1:
        return algos
    try:
        ranking = OpsRepository(cfg).get_ranking(run_id)
    except Exception:  # noqa: BLE001
        ranking = []
    ordered: list[str] = []
    for row in ranking:
        algo = str(row.get("algo", ""))
        if algo in algos and algo not in ordered:
            ordered.append(algo)
    for algo in algos:
        if algo not in ordered:
            ordered.append(algo)
    return ordered


def _algos_from_latest_inference_batch(cfg: dict[str, Any], run_cfg: dict[str, Any], run_id: str) -> list[str]:
    """run_config 학습 대상 중, 가장 최근 추론 실행 묶음(점수 mtime)만 반환."""
    configured = [str(a) for a in (run_cfg.get("algorithms") or []) if str(a).strip()]
    scored: list[tuple[str, float]] = []
    for algo in configured:
        path = inference_score_path(cfg, algo, run_id=run_id)
        if path.is_file():
            scored.append((algo, path.stat().st_mtime))
    if not scored:
        return []
    latest_mtime = max(m for _, m in scored)
    # 11_score_inference.py 가 연속 실행하는 알고리즘 묶음 (최대 ~10분 여유)
    batch_window_sec = 600.0
    return [a for a, m in scored if latest_mtime - m <= batch_window_sec]


def inference_algorithms_for_run(cfg: dict[str, Any], run_id: str) -> list[str]:
    """이 Run 추론에 사용된 algo_id 목록 (순서: 1=주, 2=보)."""
    if not run_id:
        return []
    run_cfg = load_run_config(cfg, run_id)
    saved = [str(a) for a in (run_cfg.get("inference_algorithms") or []) if str(a).strip()]
    if saved:
        return saved

    batch = _algos_from_latest_inference_batch(cfg, run_cfg, run_id)
    if batch:
        return _order_algos_by_ranking(cfg, run_id, batch)

    return []


def available_inference_algos(cfg: dict[str, Any], run_id: str | None = None) -> list[str]:
    """추론 점수 CSV가 있는 algo_id 목록 (Run별 — 이번 추론에 쓴 알고리즘만)."""
    if run_id:
        return [
            a
            for a in inference_algorithms_for_run(cfg, run_id)
            if inference_score_path(cfg, a, run_id=run_id).exists()
        ]
    algos = list_algo_ids(cfg)
    return [a for a in algos if inference_score_path(cfg, a).exists()]


def file_meta(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "mtime": "", "size_kb": 0, "rows": 0}
    stat = path.stat()
    return {
        "exists": True,
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
        "size_kb": stat.st_size // 1024,
        "path": str(path),
    }


def resolve_primary_aux(cfg: dict[str, Any], run_id: str) -> tuple[str, str]:
    """평가 순위(08) 기준 주·보조. Test ops_queue(10)용."""
    ops_cfg = dict(cfg.get("ops_queue") or {})
    try:
        return OpsRepository(cfg).get_primary_aux(run_id)
    except Exception:  # noqa: BLE001
        return (
            str(ops_cfg.get("primary_algo", "random_forest_v1")),
            str(ops_cfg.get("aux_algo", "catboost_v1")),
        )


def resolve_inference_primary_aux(cfg: dict[str, Any], run_id: str) -> tuple[str, str]:
    """추론 결과용 주·보조 — run_config.inference_algorithms 우선."""
    infer_algos = inference_algorithms_for_run(cfg, run_id) if run_id else []
    if len(infer_algos) >= 2:
        return infer_algos[0], infer_algos[1]
    if len(infer_algos) == 1:
        primary = infer_algos[0]
        _, aux = resolve_primary_aux(cfg, run_id)
        return primary, aux if aux != primary else ""
    if run_id:
        return resolve_primary_aux(cfg, run_id)
    ops_cfg = dict(cfg.get("ops_queue") or {})
    return (
        str(ops_cfg.get("primary_algo", "random_forest_v1")),
        str(ops_cfg.get("aux_algo", "catboost_v1")),
    )


def run_has_inference_step(cfg: dict[str, Any], run_id: str) -> bool:
    """Run에 inference step 성공 기록이 있을 때만 결과 표시."""
    if not run_id:
        return False
    try:
        return OpsRepository(cfg).step_succeeded(run_id, "inference")
    except Exception:  # noqa: BLE001
        return False


def _read_inference_score_csv_lite(path: Path, encoding: str, keys: list[str]) -> pd.DataFrame:
    """대시보드용 — 키·점수 컬럼만 읽어 I/O·메모리 절감."""
    header = pd.read_csv(path, encoding=encoding, nrows=0).columns.tolist()
    if SCORE_COL not in header:
        raise KeyError(f"{path.name} 에 {SCORE_COL} 없음")
    usecols = [c for c in keys if c in header] + [SCORE_COL]
    missing_keys = [k for k in keys if k not in header]
    if missing_keys:
        raise KeyError(f"{path.name} 에 키 컬럼 없음: {missing_keys}")
    return pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False, usecols=usecols)


def load_inference_queue_lite(
    cfg: dict[str, Any],
    run_id: str,
    *,
    require_step: bool = True,
) -> pd.DataFrame | None:
    """주·보조 inference 4×4 집계용 (키·점수만). 주 모델 파일 없으면 None."""
    if require_step and not run_has_inference_step(cfg, run_id):
        return None
    primary, aux = resolve_inference_primary_aux(cfg, run_id)
    primary_path = inference_score_path(cfg, primary, run_id=run_id)
    if not primary_path.exists():
        return None

    encoding = cfg.get("encoding", "EUC-KR")
    ops_cfg = dict(cfg.get("ops_queue") or {})
    keys = list(cfg.get("key_columns") or [])

    primary_df = _read_inference_score_csv_lite(primary_path, encoding, keys)
    aux_path = inference_score_path(cfg, aux, run_id=run_id)
    aux_df = None
    if aux_path.exists():
        aux_df = _read_inference_score_csv_lite(aux_path, encoding, keys)

    return build_ops_queue(primary_df, aux_df, keys, ops_cfg)


def export_inference_ops_queue(
    cfg: dict[str, Any],
    run_id: str,
    *,
    require_step: bool = True,
    infer_algos: list[str] | None = None,
) -> tuple[Path, Path, int]:
    """추론 점검 우선순위표 PK CSV·Excel 저장 + DB 적재 (3케이스·엔티티)."""
    if require_step and not run_has_inference_step(cfg, run_id):
        raise FileNotFoundError("이 Run에서 inference step이 완료되지 않았습니다.")

    algos = infer_algos or inference_algorithms_for_run(cfg, run_id)
    if not algos:
        raise FileNotFoundError("추론 알고리즘 목록이 없습니다.")

    from src.scoring.inference_capture import export_inference_capture

    pk_csv, pk_xlsx, _, _, pk_n, _ = export_inference_capture(cfg, run_id, algos)
    return pk_csv, pk_xlsx, pk_n
