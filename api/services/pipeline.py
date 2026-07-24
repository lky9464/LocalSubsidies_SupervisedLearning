"""Pipeline lock FSM and step helpers."""

from __future__ import annotations

from typing import Any

from api.state import get_pipeline_abandon
from src.pipeline.jobs import JobManager
from src.pipeline.runner import TRAIN_PIPELINE_STEPS

PREP_STEP_IDS = frozenset({"merge", "label", "preprocess", "leakage"})
TRAIN_EVAL_STEP_IDS = frozenset(
    {"train", "feature_importance", "evaluate", "ranking", "report", "ops_queue"}
)


def step_status_map(repo: Any, run_id: str) -> dict[str, str]:
    try:
        rows = repo.list_steps(run_id)
    except Exception:  # noqa: BLE001
        return {}
    return {r["step_id"]: r.get("status", "") for r in rows}


def job_is_running(cfg: dict[str, Any]) -> bool:
    try:
        job = JobManager(cfg).get_active_job(mutate=False)
    except Exception:  # noqa: BLE001
        return False
    return bool(job and job.get("status") in ("running", "starting"))


def train_eval_started(step_map: dict[str, str]) -> bool:
    return any(
        step_map.get(s) in ("running", "succeeded") for s in TRAIN_EVAL_STEP_IDS
    )


def prep_steps_all_succeeded(step_map: dict[str, str]) -> bool:
    return all(step_map.get(s) == "succeeded" for s in PREP_STEP_IDS)


def split_config_locked(step_map: dict[str, str]) -> bool:
    """01 merge 이후 분할·raw 동결 구간 — 분할 옵션 변경 금지."""
    return step_map.get("merge") in ("running", "succeeded")


def algorithms_config_editable(
    cfg: dict[str, Any], run_id: str, step_map: dict[str, str]
) -> bool:
    if get_pipeline_abandon(cfg, run_id):
        return True
    if job_is_running(cfg):
        return False
    return not train_eval_started(step_map)


def config_update_allowed(
    body: Any,
    cfg: dict[str, Any],
    run_id: str,
    step_map: dict[str, str],
) -> tuple[bool, str]:
    """Run config PUT 허용 여부 (분할 vs 알고리즘 분리)."""
    if get_pipeline_abandon(cfg, run_id):
        return True, ""
    if job_is_running(cfg):
        return False, "Job 실행 중에는 설정을 변경할 수 없습니다."

    changing_split = body.split is not None or body.split_committed is not None
    changing_algos = body.algorithms is not None or body.algorithms_committed is not None
    changing_legacy = body.options_committed is not None
    changing_extra = body.exclude_features_extra is not None

    if changing_legacy:
        if settings_locked(cfg, run_id, step_map):
            return False, "현재 설정을 변경할 수 없습니다."
        return True, ""

    if changing_split and split_config_locked(step_map):
        return (
            False,
            "데이터 가공(01) 시작 후에는 Train/Test 분할을 변경할 수 없습니다.",
        )

    if changing_algos and not algorithms_config_editable(cfg, run_id, step_map):
        return (
            False,
            "학습·평가(05~10) 시작 후에는 학습 알고리즘을 변경할 수 없습니다.",
        )

    if changing_extra and settings_locked(cfg, run_id, step_map):
        return False, "현재 설정을 변경할 수 없습니다."

    return True, ""


def settings_locked(cfg: dict[str, Any], run_id: str, step_map: dict[str, str]) -> bool:
    if get_pipeline_abandon(cfg, run_id):
        return False
    if job_is_running(cfg):
        return True

    statuses = [step_map.get(s["id"]) for s in TRAIN_PIPELINE_STEPS]
    relevant = [s for s in statuses if s]
    if not relevant:
        return False
    if any(s == "failed" for s in relevant):
        return False
    if all(step_map.get(s["id"]) == "succeeded" for s in TRAIN_PIPELINE_STEPS):
        return False
    return any(s in ("running", "succeeded") for s in relevant)


def extra_for_steps(step_ids: list[str], algos: list[str]) -> dict[str, list[str]] | None:
    if "train" not in step_ids:
        return None
    args: list[str] = []
    for a in algos:
        args.extend(["--algo", a])
    return {"train": args} if args else None
