"""RunWebNext / RestartWeb: FastAPI + static Next UI on 127.0.0.1:8600.

Usage:
  python scripts/_next_web_launcher.py           # run (foreground)
  python scripts/_next_web_launcher.py --restart # stop uvicorn then run
  python scripts/_next_web_launcher.py stop      # stop uvicorn only
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = "127.0.0.1"
PORT = 8600
HEALTH = "/api/health"
BROWSER_MARK = Path(os.environ.get("TEMP", ".")) / "lsl_next_web_browser.txt"


def _health_ok(timeout: float = 0.3) -> bool:
    url = f"http://{HOST}:{PORT}{HEALTH}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _can_bind() -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((HOST, PORT))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _python_exe() -> Path:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.exists():
        return venv
    return Path(sys.executable)


def _uvicorn_cmd() -> list[str]:
    py = _python_exe()
    return [
        str(py),
        "-m",
        "uvicorn",
        "api.main:app",
        "--host",
        HOST,
        "--port",
        str(PORT),
        "--log-level",
        "info",
    ]


def _open_browser(force: bool = False) -> None:
    url = f"http://{HOST}:{PORT}/"
    print(f"READY:{PORT}", flush=True)
    print(f"URL: {url}", flush=True)
    if not force:
        try:
            if BROWSER_MARK.exists():
                age = time.time() - BROWSER_MARK.stat().st_mtime
                if age < 20:
                    print("Browser already opened recently - skip.", flush=True)
                    return
        except OSError:
            pass
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            import webbrowser

            webbrowser.open(url)
        BROWSER_MARK.write_text(str(PORT), encoding="utf-8")
    except OSError as exc:
        print(f"WARN: browser open failed: {exc}", file=sys.stderr, flush=True)


def _stop_server() -> int:
    try:
        import psutil
    except ImportError:
        return 0
    stopped = 0
    marker = "api.main:app"
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            cmd = " ".join(str(x) for x in (proc.info.get("cmdline") or [])).lower()
            if "uvicorn" in cmd and marker in cmd:
                proc.terminate()
                stopped += 1
        except (psutil.Error, OSError):
            continue
    time.sleep(0.5)
    return stopped


def cmd_stop() -> int:
    n = _stop_server()
    print(f"Stopped {n} server(s)", flush=True)
    return 0


def cmd_run(restart: bool) -> int:
    if restart:
        n = _stop_server()
        print(f"Stopped {n} server(s)", flush=True)
        time.sleep(0.3)

    if _health_ok(timeout=0.2) and not restart:
        print("Already running — opening browser.", flush=True)
        _open_browser()
        return 0

    if not _can_bind() and not _health_ok():
        print(f"ERROR: port {PORT} in use but health check failed", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    print(f"Starting FastAPI on {HOST}:{PORT} ...", flush=True)
    # IMPORTANT: do NOT use stdout=PIPE — uvicorn logs fill the OS pipe buffer
    # and the server process deadlocks (ChunkLoadError / API timeouts).
    proc = subprocess.Popen(
        _uvicorn_cmd(),
        cwd=str(ROOT),
        env=env,
        stdout=None,
        stderr=None,
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if _health_ok():
            _open_browser()
            print("Server running. Close this window to stop.", flush=True)
            return proc.wait()
        if proc.poll() is not None:
            print("ERROR: server exited early", file=sys.stderr)
            return proc.returncode or 1
        time.sleep(0.2)
    proc.terminate()
    print("ERROR: health check timeout", file=sys.stderr)
    return 1


def main(argv: list[str] | None = None) -> int:
    args_list = list(argv if argv is not None else sys.argv[1:])
    if args_list and args_list[0] == "stop":
        return cmd_stop()
    parser = argparse.ArgumentParser()
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args(args_list)
    return cmd_run(restart=args.restart)


if __name__ == "__main__":
    raise SystemExit(main())
