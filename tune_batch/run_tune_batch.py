"""
5종 하이퍼파라미터 튜닝 일괄 실행 (scripts/12_tune_hyperparams 순차 호출).

프로젝트 루트에서:
  python tune_batch/run_tune_batch.py --run-id run_20260730_172901

설정: configs/tune.yaml (tune.algorithms, output_tag)
로그·상태: tune_batch/logs/, tune_batch/status.json
산출물: outputs/reports/tuning/{output_tag}/
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BATCH_DIR = Path(__file__).resolve().parent
LOG_DIR = BATCH_DIR / "logs"
STATUS_PATH = BATCH_DIR / "status.json"


def _ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _load_batch_context(config_path: Path | None) -> tuple[list[str], str]:
    sys.path.insert(0, str(ROOT))
    from src.io.config import load_tune_config  # noqa: WPS433

    cfg = load_tune_config(tune_path=config_path) if config_path else load_tune_config()
    tune_cfg = cfg.get("tune") or {}
    algos = [str(a) for a in (tune_cfg.get("algorithms") or [])]
    if not algos:
        raise SystemExit("tune.algorithms 가 비어 있습니다. configs/tune.yaml 을 확인하세요.")
    tag = str(cfg.get("output_tag") or "v1")
    return algos, tag


def _resolve_batch_run_id(config_path: Path | None, cli_run_id: str | None) -> str:
    sys.path.insert(0, str(ROOT))
    from src.io.config import resolve_tune_run_id, load_tune_config  # noqa: WPS433

    cfg = load_tune_config(tune_path=config_path) if config_path else load_tune_config()
    run_id = resolve_tune_run_id(cfg, cli_run_id)
    if not run_id:
        raise SystemExit(
            "run-id 가 없습니다. --run-id 또는 configs/tune.yaml data_run_id 를 지정하세요."
        )
    return run_id


def _write_status(
    *,
    log_path: Path,
    run_id: str,
    output_tag: str,
    started_at: str,
    finished_at: str | None,
    overall: str,
    algos: list[dict],
) -> None:
    payload = {
        "run_id": run_id,
        "output_tag": output_tag,
        "started_at": started_at,
        "finished_at": finished_at,
        "overall": overall,
        "log_file": str(log_path.relative_to(ROOT)),
        "tuning_output": f"outputs/reports/tuning/{output_tag}/",
        "algos": algos,
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _log_line(log_fp, msg: str) -> None:
    line = f"[{_ts()}] {msg}"
    print(line, flush=True)
    log_fp.write(line + "\n")
    log_fp.flush()


def _run_one(run_id: str, algo: str, log_fp) -> tuple[int, str | None]:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "12_tune_hyperparams.py"),
        "--run-id",
        run_id,
        "--algo",
        algo,
    ]
    _log_line(log_fp, f"START algo={algo}")
    _log_line(log_fp, f"CMD {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except OSError as exc:
        return 127, f"프로세스 시작 실패: {exc}"

    assert proc.stdout is not None
    for line in proc.stdout:
        log_fp.write(line)
        if not line.endswith("\n"):
            log_fp.write("\n")
        log_fp.flush()
        print(line, end="", flush=True)

    code = proc.wait()
    if code == 0:
        _log_line(log_fp, f"OK algo={algo} exit_code=0")
        return 0, None
    _log_line(log_fp, f"FAIL algo={algo} exit_code={code}")
    return code, f"exit_code={code}"


def main() -> int:
    parser = argparse.ArgumentParser(description="5종 하이퍼파라미터 튜닝 일괄 실행")
    parser.add_argument("--run-id", default=None, help="03 산출물 Run ID (생략 시 tune.yaml data_run_id)")
    parser.add_argument(
        "--config",
        default=None,
        help="튜닝 YAML 경로 (기본: configs/tune.yaml)",
    )
    args = parser.parse_args()
    config_path = Path(args.config).resolve() if args.config else None

    algos, output_tag = _load_batch_context(config_path)
    run_id = _resolve_batch_run_id(config_path, args.run_id)
    os.environ["LSL_RUN_ID"] = run_id
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"tune_batch_{stamp}.log"
    started_at = _ts()

    algo_states = [
        {"algo": a, "status": "pending", "exit_code": None, "error": None, "ended_at": None}
        for a in algos
    ]
    _write_status(
        log_path=log_path,
        run_id=run_id,
        output_tag=output_tag,
        started_at=started_at,
        finished_at=None,
        overall="running",
        algos=algo_states,
    )

    with log_path.open("w", encoding="utf-8") as log_fp:
        _log_line(log_fp, f"=== tune batch begin run_id={run_id} output_tag={output_tag} ===")
        _log_line(log_fp, f"python={sys.executable}")
        _log_line(log_fp, f"root={ROOT}")
        _log_line(log_fp, f"algos={algos}")
        _log_line(log_fp, f"status_file={STATUS_PATH.relative_to(ROOT)}")

        try:
            for i, algo in enumerate(algos):
                algo_states[i]["status"] = "running"
                algo_states[i]["started_at"] = _ts()
                _write_status(
                    log_path=log_path,
                    run_id=run_id,
                    output_tag=output_tag,
                    started_at=started_at,
                    finished_at=None,
                    overall="running",
                    algos=algo_states,
                )

                code, err = _run_one(run_id, algo, log_fp)
                algo_states[i]["exit_code"] = code
                algo_states[i]["ended_at"] = _ts()
                if code == 0:
                    algo_states[i]["status"] = "ok"
                else:
                    algo_states[i]["status"] = "failed"
                    algo_states[i]["error"] = err
                    _write_status(
                        log_path=log_path,
                        run_id=run_id,
                        output_tag=output_tag,
                        started_at=started_at,
                        finished_at=_ts(),
                        overall="failed",
                        algos=algo_states,
                    )
                    _log_line(log_fp, f"=== batch STOP at algo={algo} (이후 pending 유지) ===")
                    return code

            finished_at = _ts()
            _write_status(
                log_path=log_path,
                run_id=run_id,
                output_tag=output_tag,
                started_at=started_at,
                finished_at=finished_at,
                overall="completed",
                algos=algo_states,
            )
            _log_line(log_fp, "=== tune batch ALL OK ===")
            return 0

        except KeyboardInterrupt:
            _log_line(log_fp, "=== batch INTERRUPTED (KeyboardInterrupt) ===")
            for st in algo_states:
                if st["status"] == "running":
                    st["status"] = "interrupted"
                    st["ended_at"] = _ts()
                    st["error"] = "KeyboardInterrupt"
            _write_status(
                log_path=log_path,
                run_id=run_id,
                output_tag=output_tag,
                started_at=started_at,
                finished_at=_ts(),
                overall="interrupted",
                algos=algo_states,
            )
            return 130

        except Exception as exc:
            _log_line(log_fp, f"=== batch CRASH: {exc!r} ===")
            log_fp.write(traceback.format_exc())
            log_fp.flush()
            for st in algo_states:
                if st["status"] == "running":
                    st["status"] = "crashed"
                    st["ended_at"] = _ts()
                    st["error"] = repr(exc)
            _write_status(
                log_path=log_path,
                run_id=run_id,
                output_tag=output_tag,
                started_at=started_at,
                finished_at=_ts(),
                overall="crashed",
                algos=algo_states,
            )
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
