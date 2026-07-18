"""백그라운드 파이프라인 Job (페이지 이동해도 유지).

Streamlit UI는 Job JSON을 가능한 한 읽기만 하고, 상태 갱신은 워커가 담당한다.
(동시 쓰기로 JSON 깨짐·UI 스레드 블로킹 → Connection error 방지)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.io.config import PROJECT_ROOT, get_data_root
from src.ops_db.repository import OpsRepository
from src.pipeline.runner import _log_tail

_PCT_RE = re.compile(r"(\d{1,3})\s*%")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """임시 파일 후 replace — 읽기 중 깨진 JSON 방지."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(data, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass
    for _ in range(5):
        try:
            os.replace(tmp, path)
            return
        except OSError:
            time.sleep(0.05)
    # 최후: 직접 쓰기
    with open(path, "w", encoding="utf-8") as f:
        f.write(payload)


def read_json_retry(path: Path, retries: int = 8) -> dict[str, Any] | None:
    if not path.exists():
        return None
    last_err: Exception | None = None
    for i in range(retries):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            last_err = exc
            time.sleep(0.03 * (i + 1))
    if last_err:
        return None
    return None


class JobManager:
    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.repo = OpsRepository(cfg)
        self.data_root = get_data_root(cfg)

    def jobs_dir(self, run_id: str) -> Path:
        d = self.data_root / "runs" / run_id / "jobs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def active_job_path(self) -> Path:
        p = self.data_root / "runs" / "_active_job.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def job_path(self, run_id: str, job_id: str) -> Path:
        return self.jobs_dir(run_id) / f"{job_id}.json"

    def _write_job(self, job: dict[str, Any]) -> None:
        run_id = job["run_id"]
        path = self.job_path(run_id, job["job_id"])
        atomic_write_json(path, job)
        atomic_write_json(self.active_job_path(), job)

    def get_active_job(self, *, mutate: bool = False) -> dict[str, Any] | None:
        """활성 Job 조회. UI에서는 mutate=False(기본)로 읽기만 한다."""
        try:
            job = read_json_retry(self.active_job_path())
            if not job:
                return None
            return self.poll_job(
                job["job_id"], job["run_id"], mutate=mutate, base=job
            )
        except Exception:  # noqa: BLE001
            return None

    def start_steps(
        self,
        run_id: str,
        step_ids: list[str],
        *,
        extra_args_by_step: dict[str, list[str]] | None = None,
    ) -> dict[str, Any]:
        """여러 단계를 순차 실행하는 백그라운드 워커 시작."""
        active = self.get_active_job(mutate=True)
        if active and active.get("status") == "running":
            raise RuntimeError("이미 실행 중인 Job이 있습니다. 완료 후 다시 시도하세요.")

        job_id = f"job_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.repo.ensure_run(run_id)
        log_path = self.data_root / "runs" / run_id / "logs" / f"{job_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("", encoding="utf-8")

        # 워커가 바로 읽을 수 있도록 Job 파일을 먼저 기록
        job: dict[str, Any] = {
            "job_id": job_id,
            "run_id": run_id,
            "status": "starting",
            "pid": None,
            "steps": step_ids,
            "current_step": step_ids[0] if step_ids else None,
            "step_index": 0,
            "progress": 0.0,
            "started_at": _now(),
            "ended_at": None,
            "message": "워커 시작 중",
            "log_path": str(log_path),
        }
        self._write_job(job)

        worker = PROJECT_ROOT / "scripts" / "_job_worker.py"
        args = [
            sys.executable,
            str(worker),
            "--run-id",
            run_id,
            "--job-id",
            job_id,
            "--steps",
            ",".join(step_ids),
        ]
        if extra_args_by_step:
            args.extend(
                ["--extra-json", json.dumps(extra_args_by_step, ensure_ascii=False)]
            )

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["LSL_RUN_ID"] = run_id

        popen_kwargs: dict[str, Any] = {
            "args": args,
            "cwd": str(PROJECT_ROOT),
            "stdout": open(log_path, "a", encoding="utf-8", errors="replace"),
            "stderr": subprocess.STDOUT,
            "env": env,
        }
        # Streamlit과 프로세스 그룹 분리 (UI 종료/리로드 시 Job 보호)
        if sys.platform == "win32":
            # CREATE_NO_WINDOW: 콘솔 창 깜빡임 방지
            create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            popen_kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | create_no_window
            )
            popen_kwargs["close_fds"] = False
        else:
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(**popen_kwargs)
        # stdout 핸들은 자식이 쓰므로 부모에서 닫아 누수 방지
        try:
            popen_kwargs["stdout"].close()
        except Exception:  # noqa: BLE001
            pass

        job["pid"] = proc.pid
        job["status"] = "running"
        job["message"] = f"실행 중: {step_ids[0] if step_ids else '-'}"
        self._write_job(job)
        return job

    def poll_job(
        self,
        job_id: str,
        run_id: str,
        *,
        mutate: bool = False,
        base: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        path = self.job_path(run_id, job_id)
        job = read_json_retry(path) or base or {
            "job_id": job_id,
            "run_id": run_id,
            "status": "unknown",
        }

        # UI용 진행률은 메모리에서만 계산 (파일에 되쓰지 않음 → 워커와 경합 제거)
        if job.get("status") in ("running", "starting"):
            job = dict(job)
            job["progress"] = _estimate_progress(job)

            if mutate and job.get("status") == "running":
                pid = job.get("pid")
                alive = _pid_alive(int(pid)) if pid else False
                if not alive:
                    time.sleep(0.3)
                    refreshed = read_json_retry(path) or job
                    if refreshed.get("status") == "running":
                        refreshed["status"] = "failed"
                        refreshed["ended_at"] = _now()
                        refreshed["message"] = (
                            refreshed.get("message")
                            or "프로세스가 예기치 않게 종료됨"
                        )
                        self._write_job(refreshed)
                        return refreshed
                    return refreshed
        return job

    def cancel_job(
        self, job_id: str | None = None, run_id: str | None = None
    ) -> dict[str, Any]:
        """실행 중 Job 프로세스 종료 (Streamlit PID는 절대 죽이지 않음)."""
        job = self.get_active_job(mutate=False)
        if not job:
            return {"status": "unknown", "message": "활성 Job 없음"}
        if job_id and job.get("job_id") != job_id:
            return {"status": "unknown", "message": "job_id 불일치"}
        if run_id and job.get("run_id") != run_id:
            return {"status": "unknown", "message": "run_id 불일치"}
        if job.get("status") not in ("running", "starting"):
            return job

        pid = job.get("pid")
        my_pid = os.getpid()
        if pid and int(pid) != my_pid and int(pid) != os.getppid():
            _kill_pid(int(pid))

        job = dict(job)
        job["status"] = "cancelled"
        job["ended_at"] = _now()
        job["message"] = "사용자 취소"
        self._write_job(job)
        return job


def _kill_pid(pid: int) -> None:
    if pid <= 0:
        return
    if sys.platform == "win32":
        try:
            # /T: 워커가 띄운 스크립트 자식까지. Streamlit은 조상이라 영향 없음.
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                check=False,
                capture_output=True,
                timeout=15,
            )
        except Exception:  # noqa: BLE001
            pass
        return
    try:
        os.kill(pid, 15)
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    if not pid or int(pid) <= 0:
        return False
    pid = int(pid)
    if sys.platform == "win32":
        try:
            out = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                text=True,
                errors="replace",
                timeout=5,
            )
            # CSV: "name","pid",... — 정확히 해당 PID만
            return f'",{pid},"' in out.replace(" ", "") or f'"{pid}"' in out
        except Exception:  # noqa: BLE001
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _estimate_progress(job: dict[str, Any]) -> float:
    steps = job.get("steps") or []
    if not steps:
        return 0.0
    idx = int(job.get("step_index") or 0)
    base = idx / max(len(steps), 1)
    log_path = Path(job.get("log_path") or "")
    frac = 0.0
    if log_path.exists():
        try:
            tail = _log_tail(log_path, max_lines=30)
            found = _PCT_RE.findall(tail)
            if found:
                frac = min(int(found[-1]), 99) / 100.0
        except Exception:  # noqa: BLE001
            pass
    status = job.get("status")
    if status == "succeeded":
        return 1.0
    return min(0.99, base + frac / max(len(steps), 1))
