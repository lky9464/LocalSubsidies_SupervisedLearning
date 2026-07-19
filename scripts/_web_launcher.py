"""RunWeb / RestartWeb 공통: 포트 선택, 기존 서버 종료, 준비 대기.

Usage:
  python scripts/_web_launcher.py open          # 실행 중이면 READY:<port>
  python scripts/_web_launcher.py run           # 없으면 기동, READY 후 대기
  python scripts/_web_launcher.py run --restart # 종료 후 재기동
  python scripts/_web_launcher.py stop          # Streamlit 종료
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
APP = ROOT / "app" / "main.py"
HOST = "127.0.0.1"
PORTS = list(range(8501, 8511))
LAST_PORT_FILE = Path(os.environ.get("TEMP", ".")) / "lsl_web_last_port.txt"
HEALTH_PATH = "/_stcore/health"


def _health_ok(port: int, timeout: float = 0.25) -> bool:
    url = f"http://{HOST}:{port}{HEALTH_PATH}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore").strip().lower()
            return resp.status == 200 and body.startswith("ok")
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _can_bind(port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((HOST, port))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _read_last_port() -> int | None:
    try:
        text = LAST_PORT_FILE.read_text(encoding="utf-8").strip()
        port = int(text)
        if port in PORTS:
            return port
    except (OSError, ValueError):
        pass
    return None


def _save_last_port(port: int) -> None:
    try:
        LAST_PORT_FILE.write_text(str(port), encoding="utf-8")
    except OSError:
        pass


def find_running_port() -> int | None:
    last = _read_last_port()
    if last is not None and _health_ok(last, timeout=0.2):
        return last
    for port in PORTS:
        if _health_ok(port, timeout=0.15):
            return port
    return None


def pick_free_port() -> int:
    last = _read_last_port()
    if last is not None and _can_bind(last):
        return last
    for port in PORTS:
        if _can_bind(port):
            return port
    raise RuntimeError("8501~8510 포트를 사용할 수 없습니다.")


def wait_for_health(port: int, *, timeout: float = 90.0, interval: float = 0.15) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _health_ok(port, timeout=0.3):
            return True
        time.sleep(interval)
    return False


def _iter_streamlit_procs():
    import psutil

    app_marker = str(APP).lower()
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(str(x) for x in cmdline).lower()
            if "streamlit" not in joined:
                continue
            if "main.py" in joined or app_marker in joined:
                yield proc
        except (psutil.Error, OSError):
            continue


def stop_web_servers() -> int:
    import psutil

    stopped: set[int] = set()
    for proc in _iter_streamlit_procs():
        pid = proc.pid
        if pid in stopped:
            continue
        stopped.add(pid)
        try:
            proc.terminate()
        except psutil.Error:
            pass

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        alive = [p for p in _iter_streamlit_procs() if p.pid in stopped]
        if not alive:
            break
        for proc in alive:
            try:
                proc.wait(timeout=0.2)
            except psutil.TimeoutExpired:
                try:
                    proc.kill()
                except psutil.Error:
                    pass
        time.sleep(0.1)

    for port in PORTS:
        if _health_ok(port, timeout=0.1):
            for conn in psutil.net_connections(kind="inet"):
                if (
                    conn.laddr
                    and conn.laddr.port == port
                    and conn.status == psutil.CONN_LISTEN
                    and conn.pid
                ):
                    try:
                        psutil.Process(conn.pid).kill()
                        stopped.add(conn.pid)
                    except psutil.Error:
                        pass
    return len(stopped)


def _python_exe() -> Path:
    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return venv_py
    return Path(sys.executable)


def _streamlit_cmd(port: int) -> list[str]:
    py = _python_exe()
    return [
        str(py),
        "-m",
        "streamlit",
        "run",
        str(APP),
        "--server.address",
        HOST,
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
        "--server.headless",
        "true",
    ]


def _open_browser(port: int) -> None:
    url = f"http://{HOST}:{port}"
    print(f"READY:{port}", flush=True)
    print(f"URL: {url}", flush=True)
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)  # type: ignore[attr-defined]
        else:
            import webbrowser

            webbrowser.open(url)
    except OSError as exc:
        print(f"WARN: browser open failed: {exc}", file=sys.stderr, flush=True)


def cmd_open() -> int:
    port = find_running_port()
    if port is None:
        return 2
    _open_browser(port)
    return 0


def cmd_stop() -> int:
    n = stop_web_servers()
    print(f"STOPPED:{n}", file=sys.stderr, flush=True)
    return 0


def cmd_run(restart: bool) -> int:
    if restart:
        print("Stopping existing Streamlit ...", flush=True)
        stop_web_servers()
        time.sleep(0.2)

    running = find_running_port()
    if running is not None and not restart:
        print("Already running — opening browser.", flush=True)
        _open_browser(running)
        # 이미 떠 있으면 이 창은 바로 종료 (기존 서버는 유지)
        return 0

    try:
        port = pick_free_port()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return 1

    _save_last_port(port)
    print(f"Starting on {HOST}:{port} ...", flush=True)
    proc = subprocess.Popen(
        _streamlit_cmd(port),
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    if not wait_for_health(port, timeout=90.0):
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("ERROR: Streamlit health check timeout", file=sys.stderr, flush=True)
        return 1

    _open_browser(port)
    print("Server running. Close this window to stop.", flush=True)
    return proc.wait()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("open")
    sub.add_parser("stop")
    run_p = sub.add_parser("run")
    run_p.add_argument("--restart", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "open":
        return cmd_open()
    if args.cmd == "stop":
        return cmd_stop()
    if args.cmd == "run":
        return cmd_run(restart=args.restart)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
