"""로컬 웹 UI용 포트 선택. stdout에 포트 번호만 출력.

1) 건강한 Streamlit(_stcore/health=ok)이 있으면 그 포트 재사용
2) 아니면 bind 가능한 포트 중, TCP accept 좀비가 아닌 포트를 신규 기동용으로 선택
"""

from __future__ import annotations

import socket
import sys
import urllib.error
import urllib.request

HOST = "127.0.0.1"
CANDIDATES = list(range(8501, 8511))


def health_ok(port: int, timeout: float = 1.0) -> bool:
    url = f"http://{HOST}:{port}/_stcore/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore").strip().lower()
            return resp.status == 200 and body.startswith("ok")
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def can_bind(port: int) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # SO_REUSEADDR 없이 — 실제 기동과 동일한 조건에 가깝게
        s.bind((HOST, port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def accepts_tcp(port: int, timeout: float = 0.5) -> bool:
    """무언가가 TCP를 수락하면 True (좀비 listen 포함)."""
    try:
        c = socket.create_connection((HOST, port), timeout=timeout)
        c.close()
        return True
    except OSError:
        return False


def main() -> int:
    for port in CANDIDATES:
        if health_ok(port):
            print(f"reuse:{port}", file=sys.stderr)
            print(port)
            return 0

    for port in CANDIDATES:
        if not can_bind(port):
            print(f"nobind:{port}", file=sys.stderr)
            continue
        if accepts_tcp(port):
            # bind는 되는데 다른 쪽이 accept → 8501 좀비 패턴. 건너뜀
            print(f"zombie:{port}", file=sys.stderr)
            continue
        print(f"new:{port}", file=sys.stderr)
        print(port)
        return 0

    print("ERROR: 8501~8510 모두 사용 불가", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
