"""Inference endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.constants import ALGO_LABELS, PREVIEW_OPTIONS
from api.deps import get_cfg, get_job_manager, get_repo
from api.schemas.common import JobStart
from api.services.inference import (
    do_export,
    inference_algo_scores,
    inference_ops_queue_payload,
    inference_prereq,
    inference_results_meta,
    inference_trained_payload,
    missing_trained_algos,
)
from api.state import set_pipeline_abandon
from src.pipeline.run_config import freeze_raw_selection, save_inference_algorithms

router = APIRouter(prefix="/api/inference", tags=["inference"])


@router.get("/prereq")
def prereq(cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    return inference_prereq(cfg, repo)


@router.get("/trained")
def trained(run_id: str, cfg=Depends(get_cfg)) -> dict:
    return inference_trained_payload(cfg, run_id)


@router.get("/results")
def results(run_id: str, cfg=Depends(get_cfg)) -> dict:
    return inference_results_meta(cfg, run_id)


@router.get("/ops-queue")
def ops_queue(
    run_id: str,
    grade: str | None = None,
    limit: int = Query(30, ge=1, le=100),
    cfg=Depends(get_cfg),
) -> dict:
    if limit not in PREVIEW_OPTIONS:
        limit = min(PREVIEW_OPTIONS, key=lambda x: abs(x - limit))
    payload = inference_ops_queue_payload(cfg, run_id, grade=grade, limit=limit)
    primary = payload.get("primary", "")
    aux = payload.get("aux", "")
    payload["primary_label"] = ALGO_LABELS.get(primary, primary)
    payload["aux_label"] = ALGO_LABELS.get(aux, aux)
    payload["preview_limit"] = limit
    return payload


@router.get("/scores/{algo}")
def algo_scores(
    algo: str,
    limit: int = Query(30, ge=1, le=100),
    sort_desc: bool = Query(True),
    cfg=Depends(get_cfg),
) -> dict:
    if limit not in PREVIEW_OPTIONS:
        limit = min(PREVIEW_OPTIONS, key=lambda x: abs(x - limit))
    return inference_algo_scores(cfg, algo, limit=limit, sort_desc=sort_desc)


@router.post("/export")
def export_queue(run_id: str, cfg=Depends(get_cfg)) -> dict:
    try:
        return do_export(cfg, run_id)
    except FileNotFoundError as exc:
        from fastapi import HTTPException

        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        from fastapi import HTTPException

        raise HTTPException(500, str(exc)) from exc


@router.post("/run")
def run_inference(
    body: JobStart,
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
    mgr=Depends(get_job_manager),
) -> dict:
    if not body.run_id:
        from fastapi import HTTPException

        raise HTTPException(400, "Run ID가 없습니다.")
    algos = body.extra_args_by_step.get("inference") if body.extra_args_by_step else None
    if not algos:
        # extract from --algo flags in step_ids path - use algorithms from body
        pass
    algo_list = []
    if body.extra_args_by_step and "inference" in body.extra_args_by_step:
        args = body.extra_args_by_step["inference"]
        for i, a in enumerate(args):
            if a == "--algo" and i + 1 < len(args):
                algo_list.append(args[i + 1])
    if not algo_list:
        from fastapi import HTTPException

        raise HTTPException(400, "알고리즘을 1개 이상 선택하세요.")

    missing = missing_trained_algos(cfg, body.run_id, algo_list)
    if missing:
        from fastapi import HTTPException

        labels = [ALGO_LABELS.get(a, a) for a in missing]
        raise HTTPException(
            400,
            "현재 Run에서 학습되지 않은 알고리즘: "
            + ", ".join(labels)
            + ". 「학습 실행」에서 해당 알고리즘을 먼저 학습하세요.",
        )

    repo.ensure_run(body.run_id)
    set_pipeline_abandon(cfg, body.run_id, False)
    try:
        freeze_raw_selection(
            cfg,
            body.run_id,
            repo.list_selected_rel_paths(dataset_kind="inference"),
            kind="inference",
        )
        save_inference_algorithms(cfg, body.run_id, algo_list)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(400, str(exc)) from exc
    try:
        job = mgr.start_steps(
            body.run_id,
            ["inference"],
            extra_args_by_step={"inference": sum([["--algo", a] for a in algo_list], [])},
        )
    except RuntimeError as exc:
        from fastapi import HTTPException

        raise HTTPException(409, str(exc)) from exc
    return {"job_id": job.get("job_id"), "status": job.get("status")}
