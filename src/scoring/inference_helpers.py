"""추론 결과 로드·집계·Excel 내보내기 (웹 UI 공용)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src.io.config import (
    resolve_algo_score_csv,
    resolve_algo_score_top_xlsx,
    resolve_data_path,
)
from src.ops_db.repository import OpsRepository
from src.scoring.ops_queue import (
    GRADE_COL,
    build_ops_queue,
    write_ops_queue_excel,
)
from src.scoring.score_table import SCORE_COL


def inference_score_path(cfg: dict[str, Any], algo: str) -> Path:
    """scores/inference/{algo}_inference_scores.csv (구 경로 호환)."""
    return resolve_algo_score_csv(cfg, algo, "inference")


def inference_top_xlsx_path(cfg: dict[str, Any], algo: str) -> Path:
    return resolve_algo_score_top_xlsx(cfg, algo, "inference")


def inference_export_paths(cfg: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = resolve_data_path(cfg, "algorithms") / "operations"
    return out_dir / "ops_queue_inference.csv", out_dir / "ops_queue_inference.xlsx"


def available_inference_algos(cfg: dict[str, Any]) -> list[str]:
    algos = list(cfg.get("algorithms") or [])
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
    ops_cfg = dict(cfg.get("ops_queue") or {})
    try:
        return OpsRepository(cfg).get_primary_aux(run_id)
    except Exception:  # noqa: BLE001
        return (
            str(ops_cfg.get("primary_algo", "random_forest_v1")),
            str(ops_cfg.get("aux_algo", "catboost_v1")),
        )


def run_has_inference_step(cfg: dict[str, Any], run_id: str) -> bool:
    """점수 파일은 전역(scores/inference)이라, Run에 inference step 성공 기록이 있을 때만 표시."""
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


def load_inference_queue_lite(cfg: dict[str, Any], run_id: str) -> pd.DataFrame | None:
    """주·보조 inference 4×4 집계용 (키·점수만). 주 모델 파일 없으면 None."""
    if not run_has_inference_step(cfg, run_id):
        return None
    primary, aux = resolve_primary_aux(cfg, run_id)
    primary_path = inference_score_path(cfg, primary)
    if not primary_path.exists():
        return None

    encoding = cfg.get("encoding", "EUC-KR")
    ops_cfg = dict(cfg.get("ops_queue") or {})
    keys = list(cfg.get("key_columns") or [])

    primary_df = _read_inference_score_csv_lite(primary_path, encoding, keys)
    aux_path = inference_score_path(cfg, aux)
    aux_df = None
    if aux_path.exists():
        aux_df = _read_inference_score_csv_lite(aux_path, encoding, keys)

    return build_ops_queue(primary_df, aux_df, keys, ops_cfg)


def load_inference_queue(cfg: dict[str, Any], run_id: str) -> pd.DataFrame | None:
    """주·보조 inference 점수로 우선순위표 생성. 주 모델 파일 없으면 None."""
    if not run_has_inference_step(cfg, run_id):
        return None
    primary, aux = resolve_primary_aux(cfg, run_id)
    primary_path = inference_score_path(cfg, primary)
    if not primary_path.exists():
        return None

    encoding = cfg.get("encoding", "EUC-KR")
    ops_cfg = dict(cfg.get("ops_queue") or {})
    keys = list(cfg.get("key_columns") or [])

    primary_df = pd.read_csv(primary_path, encoding=encoding, dtype=str, low_memory=False)
    aux_path = inference_score_path(cfg, aux)
    aux_df = None
    if aux_path.exists():
        aux_df = pd.read_csv(aux_path, encoding=encoding, dtype=str, low_memory=False)

    return build_ops_queue(primary_df, aux_df, keys, ops_cfg)


def inference_grade_counts(queue: pd.DataFrame) -> dict[str, int]:
    if queue.empty or GRADE_COL not in queue.columns:
        return {}
    from src.scoring.ops_queue import PRIMARY_LABELS

    vc = queue[GRADE_COL].value_counts()
    return {g: int(vc.get(g, 0)) for g in PRIMARY_LABELS}


def export_inference_ops_queue(cfg: dict[str, Any], run_id: str) -> tuple[Path, Path, int]:
    """추론 점검 우선순위표 CSV·Excel 저장 (구간 규칙은 10과 동일, 시트는 추론용)."""
    queue = load_inference_queue(cfg, run_id)
    if queue is None or queue.empty:
        primary, _ = resolve_primary_aux(cfg, run_id)
        raise FileNotFoundError(
            f"주 모델 scores/inference/{primary}_inference_scores.csv 가 없습니다."
        )

    csv_path, xlsx_path = inference_export_paths(cfg)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    encoding = cfg.get("encoding", "EUC-KR")
    queue.to_csv(csv_path, index=False, encoding=encoding)
    write_ops_queue_excel(queue, xlsx_path, mode="inference")
    return csv_path, xlsx_path, len(queue)


def dashboard_inference_line(cfg: dict[str, Any], run_id: str) -> str | None:
    """대시보드 한 줄 요약. 없으면 None."""
    if not run_has_inference_step(cfg, run_id):
        return None
    available = available_inference_algos(cfg)
    if not available:
        return None

    primary, _ = resolve_primary_aux(cfg, run_id)
    primary_path = inference_score_path(cfg, primary)
    meta = file_meta(primary_path)
    if not meta["exists"]:
        algos = ", ".join(available[:3])
        return f"추론 결과: {algos} 등 {len(available)}종 (주 모델 파일 없음)"

    try:
        queue = load_inference_queue(cfg, run_id)
    except Exception:  # noqa: BLE001
        return f"추론 결과: 주 모델 파일 있음 · 등급 집계 실패 ({meta['mtime']})"

    if queue is None:
        return None

    counts = inference_grade_counts(queue)
    total = len(queue)
    return (
        f"추론 {total:,}건 · 주A={counts.get('주A', 0):,} "
        f"주B={counts.get('주B', 0):,} 주C={counts.get('주C', 0):,} "
        f"· 갱신 {meta['mtime']}"
    )
