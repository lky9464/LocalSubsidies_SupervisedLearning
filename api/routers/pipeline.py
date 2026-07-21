"""Run steps and pipeline config."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.constants import ALGO_LABELS
from api.deps import get_cfg, get_job_manager, get_repo
from api.schemas.common import LeakageResume, PipelineAbandonUpdate, RunConfigUpdate
from api.serializers import df_to_records
from api.services.pipeline import (
    extra_for_steps,
    settings_locked,
    step_status_map,
)
from api.state import get_opts_edit, get_pipeline_abandon, set_opts_edit, set_pipeline_abandon
from src.io.config import resolve_repo_path
from src.models.registry import build_algo_labels_map, normalize_algo_id
from src.pipeline.run_config import (
    freeze_raw_selection,
    load_run_config,
    run_config_path,
    save_run_config,
    warn_test_share,
)
from src.pipeline.runner import TRAIN_PIPELINE_STEPS

router = APIRouter(tags=["pipeline"])


def _split_summary(split: dict) -> str:
    mode = split.get("mode", "time")
    if mode == "random":
        return f"랜덤 · test_size={split.get('test_size', 0.3)}"
    return (
        f"기간 · Train {split.get('train_start')}~{split.get('train_end')} / "
        f"Test {split.get('test_start')}~{split.get('test_end')}"
    )


@router.get("/api/runs/{run_id}/steps")
def list_steps(run_id: str, repo=Depends(get_repo)) -> dict:
    try:
        steps = repo.list_steps(run_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"단계 상태 조회 실패: {exc}") from exc
    return {"steps": steps}


@router.get("/api/runs/{run_id}/config")
def get_config(run_id: str, cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    run_cfg = load_run_config(cfg, run_id)
    step_map = step_status_map(repo, run_id)
    locked = settings_locked(cfg, run_id, step_map)
    split = run_cfg.get("split") or {}
    algos = [normalize_algo_id(a) for a in (run_cfg.get("algorithms") or [])]
    labels_map = build_algo_labels_map(cfg)
    warn = None
    if split.get("mode", "time") == "time":
        warn = warn_test_share(
            split.get("train_start", ""),
            split.get("train_end", ""),
            split.get("test_start", ""),
            split.get("test_end", ""),
        )
    selected_raw = repo.list_selected_rel_paths(dataset_kind="train")
    frozen_raw = [str(x) for x in (run_cfg.get("raw_files") or [])]
    return {
        "run_id": run_id,
        "config": run_cfg,
        "committed": bool(run_cfg.get("options_committed")),
        "locked": locked,
        "opts_edit": get_opts_edit(cfg, run_id),
        "pipeline_abandon": get_pipeline_abandon(cfg, run_id),
        "split_summary": _split_summary(split),
        "algo_labels": [labels_map.get(a, ALGO_LABELS.get(a, a)) for a in algos],
        "config_exists": run_config_path(cfg, run_id).exists(),
        "warn_test_share": warn,
        "steps": TRAIN_PIPELINE_STEPS,
        "step_status": step_map,
        "selected_raw_files": selected_raw,
        "frozen_raw_files": frozen_raw,
    }


@router.put("/api/runs/{run_id}/config")
def put_config(run_id: str, body: RunConfigUpdate, cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    run_cfg = load_run_config(cfg, run_id)
    step_map = step_status_map(repo, run_id)
    if settings_locked(cfg, run_id, step_map):
        raise HTTPException(423, "현재 설정을 변경할 수 없습니다.")

    if body.split is not None:
        run_cfg["split"] = {**(run_cfg.get("split") or {}), **body.split}
        if run_cfg["split"].get("mode") == "random":
            run_cfg["split"]["random_state"] = 42
    if body.algorithms is not None:
        if len(body.algorithms) < 2:
            raise HTTPException(400, "알고리즘을 2개 이상 선택하세요.")
        run_cfg["algorithms"] = [normalize_algo_id(a) for a in body.algorithms]
    if body.options_committed is not None:
        run_cfg["options_committed"] = body.options_committed
    if body.exclude_features_extra is not None:
        run_cfg["exclude_features_extra"] = body.exclude_features_extra

    save_run_config(cfg, run_id, run_cfg)
    if body.options_committed:
        set_opts_edit(cfg, run_id, False)
    return {"ok": True, "config": run_cfg}


@router.post("/api/runs/{run_id}/pipeline/abandon")
def pipeline_abandon(run_id: str, body: PipelineAbandonUpdate, cfg=Depends(get_cfg)) -> dict:
    set_pipeline_abandon(cfg, run_id, body.abandon)
    if body.opts_edit:
        set_opts_edit(cfg, run_id, True)
    return {"ok": True}


@router.post("/api/runs/{run_id}/pipeline/reopen")
def pipeline_reopen(run_id: str, cfg=Depends(get_cfg)) -> dict:
    set_opts_edit(cfg, run_id, True)
    return {"ok": True}


@router.get("/api/runs/{run_id}/leakage")
def get_leakage(run_id: str, cfg=Depends(get_cfg)) -> dict:
    summary_path = resolve_repo_path(cfg, "reports_comparison") / "leakage_audit_summary.json"
    if not summary_path.exists():
        return {"available": False}
    try:
        with open(summary_path, encoding="utf-8") as f:
            meta = json.load(f)
    except OSError:
        return {"available": False}

    verdict = meta.get("verdict", "")
    suspects = list(meta.get("suspect_features") or [])
    forbidden = list(meta.get("forbidden_in_features") or [])
    features = sorted(set(forbidden + suspects))
    show = bool(str(verdict).startswith("FAIL") or suspects or forbidden)
    return {
        "available": show,
        "verdict": verdict,
        "features": features[:40],
        "all_features": features,
        "default_selected": forbidden,
    }


@router.post("/api/runs/{run_id}/leakage/resume")
def leakage_resume(
    run_id: str,
    body: LeakageResume,
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
    mgr=Depends(get_job_manager),
) -> dict:
    rc = load_run_config(cfg, run_id)
    extra = list(rc.get("exclude_features_extra") or [])
    for f in body.features:
        if f not in extra:
            extra.append(f)
    rc["exclude_features_extra"] = extra
    save_run_config(cfg, run_id, rc)
    repo.upsert_step(
        run_id,
        "leakage_remediation",
        "succeeded",
        message=f"제외 {len(body.features)}개 후 03부터 재개",
        ended=True,
    )
    try:
        job = mgr.start_steps(run_id, ["preprocess", "leakage"])
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "job_id": job.get("job_id")}


@router.post("/api/runs/{run_id}/pipeline/start")
def pipeline_start(
    run_id: str,
    payload: dict[str, Any],
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
    mgr=Depends(get_job_manager),
) -> dict:
    """Start steps with optional train algo extras."""
    step_ids = payload.get("step_ids") or []
    if not step_ids:
        raise HTTPException(400, "step_ids required")
    run_cfg = load_run_config(cfg, run_id)
    algos = list(run_cfg.get("algorithms") or [])
    if "train" in step_ids and len(algos) < 2:
        raise HTTPException(400, "학습 알고리즘을 2개 이상 선택하세요.")

    # 01 merge 가 포함된 실행이면 현재 데이터 선택을 run_config에 동결
    if "merge" in step_ids:
        try:
            run_cfg = freeze_raw_selection(
                cfg,
                run_id,
                repo.list_selected_rel_paths(dataset_kind="train"),
                kind="train",
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    run_cfg["options_committed"] = True
    save_run_config(cfg, run_id, run_cfg)
    set_pipeline_abandon(cfg, run_id, False)
    set_opts_edit(cfg, run_id, False)

    try:
        job = mgr.start_steps(
            run_id,
            step_ids,
            extra_args_by_step=extra_for_steps(step_ids, algos),
        )
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"job_id": job.get("job_id"), "status": job.get("status")}
