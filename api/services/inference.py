"""Inference helpers for API (wraps app logic without Streamlit)."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.scoring.inference_helpers import (
    available_inference_algos,
    export_inference_ops_queue,
    file_meta,
    inference_export_paths,
    inference_score_path,
    inference_top_xlsx_path,
    load_inference_queue,
    load_inference_queue_lite,
    resolve_primary_aux,
    run_has_inference_step,
)
from api.constants import ALGO_LABELS
from api.serializers import df_to_records, matrix_to_payload
from src.io.config import resolve_algo_dir
from src.ops_db.repository import OpsRepository
from src.pipeline.run_config import load_run_config
from src.scoring.ops_queue import GRADE_COL, PRIMARY_LABELS, summarize_matrix, summarize_ops_queue
from src.scoring.score_table import SCORE_COL


def inference_prereq(cfg: dict[str, Any]) -> dict[str, Any]:
    raw_dir = __import__("src.io.config", fromlist=["get_data_root"]).get_data_root(cfg) / "raw_inference"
    csvs = list(raw_dir.glob("*.csv")) if raw_dir.exists() else []
    return {"has_data": len(csvs) > 0, "file_count": len(csvs)}


def trained_algos_for_run(cfg: dict[str, Any], run_id: str) -> list[str]:
    """현재 Run에서 train step 성공 + run_config 알고리즘 + model.joblib 존재."""
    if not run_id:
        return []
    repo = OpsRepository(cfg)
    if not repo.step_succeeded(run_id, "train"):
        return []
    run_cfg = load_run_config(cfg, run_id)
    configured = [str(a) for a in (run_cfg.get("algorithms") or [])]
    trained: list[str] = []
    for algo in configured:
        model_path = resolve_algo_dir(cfg, algo) / "model.joblib"
        if model_path.is_file():
            trained.append(algo)
    return trained


def inference_trained_payload(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    trained = trained_algos_for_run(cfg, run_id)
    repo = OpsRepository(cfg)
    train_ok = bool(run_id) and repo.step_succeeded(run_id, "train")
    trained_set = set(trained)
    primary, aux = ("", "")
    if run_id:
        primary, aux = repo.get_primary_aux(run_id)
    # 평가순위 주(1위)·보(2위) 중 이 Run에서 학습된 것만 기본 선택
    defaults: list[str] = []
    if primary in trained_set:
        defaults.append(primary)
    if aux in trained_set and aux not in defaults:
        defaults.append(aux)
    return {
        "run_id": run_id,
        "train_succeeded": train_ok,
        "trained": trained,
        "trained_labels": {a: ALGO_LABELS.get(a, a) for a in trained},
        "primary": primary if primary in trained_set else None,
        "aux": aux if aux in trained_set else None,
        "primary_label": ALGO_LABELS.get(primary, primary) if primary in trained_set else None,
        "aux_label": ALGO_LABELS.get(aux, aux) if aux in trained_set else None,
        "defaults": defaults,
    }


def missing_trained_algos(
    cfg: dict[str, Any], run_id: str, selected: list[str]
) -> list[str]:
    trained = set(trained_algos_for_run(cfg, run_id))
    return [a for a in selected if a not in trained]


def inference_results_meta(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    if not run_has_inference_step(cfg, run_id):
        return {
            "available": [],
            "empty": True,
            "run_inference_missing": True,
            "expected_path_hint": "이 Run에서 「추론 실행」을 완료한 뒤 결과가 표시됩니다.",
        }
    available = available_inference_algos(cfg)
    if not available:
        primary, _ = resolve_primary_aux(cfg, run_id)
        return {
            "available": [],
            "empty": True,
            "expected_path_hint": f"scores/inference/{primary}_inference_scores.csv",
        }

    rows = []
    for algo in available:
        score_path = inference_score_path(cfg, algo)
        top_path = inference_top_xlsx_path(cfg, algo)
        sm = file_meta(score_path)
        tm = file_meta(top_path)
        rows.append(
            {
                "algo": algo,
                "algo_label": algo,
                "score_exists": sm["exists"],
                "score_mtime": sm.get("mtime", ""),
                "score_size_kb": sm.get("size_kb", 0),
                "top_xlsx_exists": tm["exists"],
                "top_xlsx_mtime": tm.get("mtime", ""),
            }
        )
    return {"available": rows, "empty": False}


def dashboard_inference_block(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    """대시보드용 — 4×4 매트릭스만 (키·점수 컬럼만 읽음)."""
    primary, aux = resolve_primary_aux(cfg, run_id)
    if not run_has_inference_step(cfg, run_id):
        return {
            "empty": True,
            "primary": primary,
            "aux": aux,
            "run_inference_missing": True,
        }
    try:
        queue = load_inference_queue_lite(cfg, run_id)
    except Exception:  # noqa: BLE001
        return {"empty": True, "primary": primary, "aux": aux}

    if queue is None or queue.empty:
        return {"empty": True, "primary": primary, "aux": aux}

    return {
        "empty": False,
        "total": len(queue),
        "primary": primary,
        "aux": aux,
        "matrix": matrix_to_payload(summarize_matrix(queue)),
    }


def inference_ops_queue_payload(
    cfg: dict[str, Any],
    run_id: str,
    *,
    grade: str | None = None,
    limit: int = 30,
) -> dict[str, Any]:
    primary, aux = resolve_primary_aux(cfg, run_id)
    try:
        queue = load_inference_queue(cfg, run_id)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "primary": primary, "aux": aux}

    if queue is None or queue.empty:
        return {"empty": True, "primary": primary, "aux": aux}

    matrix_df = summarize_matrix(queue)
    summary_df = summarize_ops_queue(queue)

    preview = queue
    if grade and grade != "(전체)":
        preview = preview[preview[GRADE_COL] == grade]
    preview = preview.head(limit)

    return {
        "primary": primary,
        "aux": aux,
        "total": len(queue),
        "matrix": matrix_to_payload(matrix_df),
        "summary": df_to_records(summary_df),
        "preview_columns": list(preview.columns),
        "preview_rows": preview.where(pd.notnull(preview), None).to_dict(orient="records"),
        "grade_counts": {
            g: int((queue[GRADE_COL] == g).sum()) for g in PRIMARY_LABELS if GRADE_COL in queue.columns
        },
    }


def inference_algo_scores(
    cfg: dict[str, Any],
    algo: str,
    *,
    limit: int = 30,
    sort_desc: bool = True,
) -> dict[str, Any]:
    path = inference_score_path(cfg, algo)
    if not path.exists():
        return {"empty": True}

    encoding = cfg.get("encoding", "EUC-KR")
    df = pd.read_csv(path, encoding=encoding, dtype=str, low_memory=False)
    n = len(df)
    scores = pd.to_numeric(df.get(SCORE_COL), errors="coerce")
    avg = float(scores.mean()) if scores.notna().any() else None
    mx = float(scores.max()) if scores.notna().any() else None
    top1 = int(max(1, n // 100)) if n else 0

    crtr = None
    if "CRTR_YM" in df.columns:
        vc = df["CRTR_YM"].value_counts().head(20)
        crtr = [{"CRTR_YM": str(k), "건수": int(v)} for k, v in vc.items()]

    if sort_desc and SCORE_COL in df.columns:
        df = df.copy()
        df["_sort"] = pd.to_numeric(df[SCORE_COL], errors="coerce")
        df = df.sort_values("_sort", ascending=False, na_position="last").drop(columns=["_sort"])

    preview = df.head(limit)
    return {
        "row_count": n,
        "avg_score": avg,
        "max_score": mx,
        "top1_est": top1,
        "crtr_ym": crtr,
        "preview_columns": list(preview.columns),
        "preview_rows": preview.where(pd.notnull(preview), None).to_dict(orient="records"),
    }


def do_export(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    csv_path, xlsx_path, n = export_inference_ops_queue(cfg, run_id)
    return {
        "row_count": n,
        "csv_basename": csv_path.name,
        "xlsx_basename": xlsx_path.name,
        "export_dir_hint": "algorithms/operations/",
    }
