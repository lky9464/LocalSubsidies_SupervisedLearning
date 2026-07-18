"""백그라운드 순차 단계 실행 워커 (UI에서 직접 실행하지 않음)."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.config import PROJECT_ROOT, load_config  # noqa: E402
from src.ops_db.repository import OpsRepository  # noqa: E402
from src.pipeline.jobs import JobManager, atomic_write_json, read_json_retry  # noqa: E402
from src.pipeline.runner import STEP_BY_ID, _log_tail  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _save_job(mgr: JobManager, job: dict) -> None:
    path = mgr.job_path(job["run_id"], job["job_id"])
    atomic_write_json(path, job)
    atomic_write_json(mgr.active_job_path(), job)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--steps", required=True)
    parser.add_argument("--extra-json", default="{}")
    args = parser.parse_args()

    cfg = load_config()
    mgr = JobManager(cfg)
    repo = OpsRepository(cfg)
    run_id = args.run_id
    job_id = args.job_id
    step_ids = [s for s in args.steps.split(",") if s]
    extra = json.loads(args.extra_json or "{}")

    job_path = mgr.job_path(run_id, job_id)
    job = None
    for _ in range(50):
        job = read_json_retry(job_path)
        if job:
            break
        time.sleep(0.1)
    if not job:
        print(f"[worker] job 파일 없음: {job_path}", file=sys.stderr)
        sys.exit(2)

    job["status"] = "running"
    job["pid"] = os.getpid()
    job["message"] = "워커 실행 중"
    _save_job(mgr, job)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["LSL_RUN_ID"] = run_id

    for i, step_id in enumerate(step_ids):
        if step_id not in STEP_BY_ID:
            job["status"] = "failed"
            job["ended_at"] = _now()
            job["message"] = f"알 수 없는 단계: {step_id}"
            _save_job(mgr, job)
            sys.exit(2)

        step = STEP_BY_ID[step_id]
        script = PROJECT_ROOT / step["script"]
        log_path = Path(job["log_path"])
        job["current_step"] = step_id
        job["step_index"] = i
        job["progress"] = i / max(len(step_ids), 1)
        job["message"] = f"실행 중: {step['label']}"
        _save_job(mgr, job)

        try:
            repo.upsert_step(
                run_id, step_id, "running", started=True, log_path=str(log_path)
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[worker] DB upsert 경고: {exc}", file=sys.stderr)

        cmd = [sys.executable, str(script), *extra.get(step_id, [])]
        with open(log_path, "a", encoding="utf-8", errors="replace") as logf:
            logf.write(f"\n\n===== {step['label']} =====\n$ {' '.join(cmd)}\n")
            logf.flush()
            proc = subprocess.run(
                cmd,
                cwd=str(PROJECT_ROOT),
                stdout=logf,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                check=False,
            )
        if proc.returncode != 0:
            tail = _log_tail(log_path, 40)
            job["status"] = "failed"
            job["ended_at"] = _now()
            job["message"] = f"{step_id} 실패 exit={proc.returncode}\n{tail}"
            job["progress"] = i / max(len(step_ids), 1)
            _save_job(mgr, job)
            try:
                repo.upsert_step(
                    run_id, step_id, "failed", message=job["message"][:2000], ended=True
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[worker] DB upsert 경고: {exc}", file=sys.stderr)
            sys.exit(proc.returncode)

        try:
            repo.upsert_step(run_id, step_id, "succeeded", ended=True)
        except Exception as exc:  # noqa: BLE001
            print(f"[worker] DB upsert 경고: {exc}", file=sys.stderr)

    job["status"] = "succeeded"
    job["ended_at"] = _now()
    job["progress"] = 1.0
    job["current_step"] = None
    job["message"] = "모든 단계 완료"
    _save_job(mgr, job)


if __name__ == "__main__":
    main()
