"""로컬 파이프라인 Job Runner (스크립트 경로·단계 정의)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.io.config import PROJECT_ROOT, get_data_root
from src.ops_db.repository import OpsRepository

# 실행 순서 = 파일 번호 (추론 11은 학습 파이프라인 UI에서 제외)
PIPELINE_STEPS: list[dict[str, str]] = [
    {"id": "merge", "script": "scripts/01_merge_raw.py", "label": "01 원본 통합", "num": 1},
    {"id": "label", "script": "scripts/02_fix_target.py", "label": "02 타겟 수정", "num": 2},
    {"id": "preprocess", "script": "scripts/03_preprocess.py", "label": "03 전처리", "num": 3},
    {"id": "leakage", "script": "scripts/04_leakage_audit.py", "label": "04 누수점검", "num": 4},
    {"id": "train", "script": "scripts/05_train.py", "label": "05 학습", "num": 5},
    {"id": "feature_importance", "script": "scripts/06_feature_importance.py", "label": "06 Feature중요도", "num": 6},
    {"id": "evaluate", "script": "scripts/07_evaluate.py", "label": "07 평가·점수", "num": 7},
    {"id": "ranking", "script": "scripts/08_update_ranking.py", "label": "08 모델 순위", "num": 8},
    {"id": "report", "script": "scripts/09_report.py", "label": "09 리포트", "num": 9},
    {"id": "ops_queue", "script": "scripts/10_ops_queue.py", "label": "10 타겟 포착 분포", "num": 10},
    {"id": "inference", "script": "scripts/11_score_inference.py", "label": "11 추론", "num": 11},
]

TRAIN_PIPELINE_STEPS = [s for s in PIPELINE_STEPS if s["id"] != "inference"]
STEP_BY_ID = {s["id"]: s for s in PIPELINE_STEPS}


def new_run_id() -> str:
    return datetime.now().strftime("run_%Y%m%d_%H%M%S")


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _log_tail(log_path: Path, max_lines: int = 40) -> str:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-max_lines:])


class PipelineRunner:
    """동기 실행(하위 호환). 웹 UI는 jobs.JobManager 사용 권장."""

    def __init__(self, cfg: dict[str, Any]) -> None:
        self.cfg = cfg
        self.repo = OpsRepository(cfg)
        self.data_root = get_data_root(cfg)

    def runs_dir(self, run_id: str) -> Path:
        d = self.data_root / "runs" / run_id
        d.mkdir(parents=True, exist_ok=True)
        (d / "logs").mkdir(parents=True, exist_ok=True)
        return d

    def status_path(self, run_id: str) -> Path:
        return self.runs_dir(run_id) / "status.json"

    def read_status(self, run_id: str) -> dict[str, Any]:
        p = self.status_path(run_id)
        if not p.exists():
            return {"run_id": run_id, "steps": {}}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def read_log_tail(self, run_id: str, step_id: str, max_lines: int = 60) -> tuple[str, Path]:
        log_path = self.runs_dir(run_id) / "logs" / f"{step_id}.log"
        return _log_tail(log_path, max_lines=max_lines), log_path

    def _write_status(self, run_id: str, status: dict[str, Any]) -> None:
        with open(self.status_path(run_id), "w", encoding="utf-8") as f:
            json.dump(status, f, ensure_ascii=False, indent=2)

    def run_step(
        self,
        step_id: str,
        run_id: str,
        *,
        extra_args: list[str] | None = None,
    ) -> dict[str, Any]:
        if step_id not in STEP_BY_ID:
            raise KeyError(f"알 수 없는 단계: {step_id}")
        step = STEP_BY_ID[step_id]
        script = PROJECT_ROOT / step["script"]
        if not script.exists():
            raise FileNotFoundError(script)

        self.repo.ensure_run(run_id)
        log_path = self.runs_dir(run_id) / "logs" / f"{step_id}.log"
        status = self.read_status(run_id)
        status.setdefault("steps", {})
        status["steps"][step_id] = {
            "status": "running",
            "started_at": _now(),
            "log_path": str(log_path),
        }
        self._write_status(run_id, status)
        self.repo.upsert_step(run_id, step_id, "running", log_path=str(log_path), started=True)

        cmd = [sys.executable, str(script), *(extra_args or [])]
        env = os.environ.copy()
        env["PYTHONIOBINARY"] = "utf-8"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["LSL_RUN_ID"] = run_id
        try:
            with open(log_path, "w", encoding="utf-8", errors="replace") as logf:
                logf.write(f"$ {' '.join(cmd)}\n\n")
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
            ok = proc.returncode == 0
            st = "succeeded" if ok else "failed"
            tail = _log_tail(log_path, max_lines=40)
            msg = f"exit={proc.returncode}"
            if not ok and tail:
                msg = f"{msg}\n{tail}"
            status["steps"][step_id].update(
                {
                    "status": st,
                    "ended_at": _now(),
                    "message": msg,
                    "log_path": str(log_path),
                    "log_tail": tail,
                }
            )
            self._write_status(run_id, status)
            self.repo.upsert_step(
                run_id, step_id, st, message=msg[:2000], log_path=str(log_path), ended=True
            )
            return status["steps"][step_id]
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            status["steps"][step_id].update(
                {"status": "failed", "ended_at": _now(), "message": msg}
            )
            self._write_status(run_id, status)
            self.repo.upsert_step(
                run_id, step_id, "failed", message=msg, log_path=str(log_path), ended=True
            )
            raise
