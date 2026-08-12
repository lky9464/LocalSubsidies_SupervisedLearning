"""Inference helpers for API (wraps app logic without Streamlit)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.scoring.inference_capture import allowed_inference_role_algos
from src.scoring.inference_helpers import (
    available_inference_algos,
    file_meta,
    inference_score_path,
    inference_top_xlsx_path,
    resolve_inference_primary_aux,
    run_has_inference_step,
)
from api.constants import ALGO_LABELS
from api.serializers import matrix_to_payload
from src.io.config import resolve_algo_dir
from src.ops_db.repository import OpsRepository
from src.pipeline.run_config import load_run_config
from src.scoring.ops_capture import CASE_PRIMARY_AUX


def inference_prereq(cfg: dict[str, Any], repo: OpsRepository | None = None) -> dict[str, Any]:
    """선택(selected)된 추론 CSV 기준. 레지스트리 없으면 폴더 glob 폴백."""
    if repo is None:
        repo = OpsRepository(cfg)
    selected = repo.list_selected_rel_paths(dataset_kind="inference")
    if selected:
        return {
            "has_data": True,
            "file_count": len(selected),
            "selected_files": [Path(p).name for p in selected],
        }
    raw_dir = (
        __import__("src.io.config", fromlist=["get_data_root"]).get_data_root(cfg)
        / "raw_inference"
    )
    csvs = list(raw_dir.glob("*.csv")) if raw_dir.exists() else []
    return {
        "has_data": False,
        "file_count": len(csvs),
        "selected_files": [],
        "message": "데이터 등록에서 추론 CSV를 선택한 뒤 「선택 저장」하세요."
        if csvs
        else "등록·선택된 추론 CSV가 없습니다.",
    }


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
        model_path = resolve_algo_dir(cfg, algo, run_id=run_id) / "model.joblib"
        if model_path.is_file():
            trained.append(algo)
    return trained


def inference_trained_payload(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    trained = trained_algos_for_run(cfg, run_id)
    repo = OpsRepository(cfg)
    train_ok = bool(run_id) and repo.step_succeeded(run_id, "train")
    trained_set = set(trained)
    roles = repo.get_roles(run_id) if run_id else {}
    primary = roles.get("primary") or ""
    aux = roles.get("aux") or ""
    reference = roles.get("reference") or ""

    allowed = allowed_inference_role_algos(cfg, run_id)
    defaults = [a for a in allowed if a in trained_set]

    return {
        "run_id": run_id,
        "train_succeeded": train_ok,
        "trained": trained,
        "trained_labels": {a: ALGO_LABELS.get(a, a) for a in trained},
        "primary": primary if primary in trained_set else None,
        "aux": aux if aux in trained_set else None,
        "reference": reference if reference in trained_set else None,
        "primary_label": ALGO_LABELS.get(primary, primary) if primary in trained_set else None,
        "aux_label": ALGO_LABELS.get(aux, aux) if aux in trained_set else None,
        "reference_label": ALGO_LABELS.get(reference, reference)
        if reference in trained_set
        else None,
        "allowed": allowed,
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
    available = available_inference_algos(cfg, run_id)
    if not available:
        primary, _ = resolve_inference_primary_aux(cfg, run_id)
        return {
            "available": [],
            "empty": True,
            "expected_path_hint": f"scores/inference/{primary}_inference_scores.csv",
        }

    rows = []
    for algo in available:
        score_path = inference_score_path(cfg, algo, run_id=run_id)
        top_path = inference_top_xlsx_path(cfg, algo, run_id=run_id)
        sm = file_meta(score_path)
        tm = file_meta(top_path)
        rows.append(
            {
                "algo": algo,
                "algo_label": ALGO_LABELS.get(algo, algo),
                "score_exists": sm["exists"],
                "score_mtime": sm.get("mtime", ""),
                "score_size_kb": sm.get("size_kb", 0),
                "top_xlsx_exists": tm["exists"],
                "top_xlsx_mtime": tm.get("mtime", ""),
            }
        )
    return {"available": rows, "empty": False}


def dashboard_inference_block(cfg: dict[str, Any], run_id: str) -> dict[str, Any]:
    """대시보드용 — primary_aux PK 4×4 (DB 우선)."""
    primary, aux = resolve_inference_primary_aux(cfg, run_id)
    if not run_has_inference_step(cfg, run_id):
        return {
            "empty": True,
            "primary": primary,
            "aux": aux,
            "run_inference_missing": True,
        }

    repo = OpsRepository(cfg)
    try:
        mat_all, _, meta = repo.inference_capture_matrices(
            run_id, CASE_PRIMARY_AUX, unit="pk"
        )
        if meta.get("total", 0) > 0:
            return {
                "empty": False,
                "total": meta["total"],
                "primary": primary,
                "aux": aux,
                "matrix": matrix_to_payload(mat_all),
            }
    except Exception:  # noqa: BLE001
        pass

    from src.scoring.inference_helpers import load_inference_queue_lite
    from src.scoring.ops_queue import summarize_matrix

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
