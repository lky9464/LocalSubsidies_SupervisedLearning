"""민감데이터 처리 스크립트 공통 배너."""

from __future__ import annotations

import sys

# Windows cp949 콘솔/리다이렉트에서도 깨지지 않도록 ASCII 하이픈 사용
BANNER = """
================================================================
[주의] 민감데이터 처리 스크립트 - 사용자 PC 로컬 전용
- Cursor Agent가 이 스크립트를 실행하거나 raw/행 데이터를 읽지 마세요.
- 데이터는 프로젝트 밖 data_root에만 두고 GitHub에 올리지 마세요.
================================================================
"""


def safe_print(text: str) -> None:
    """콘솔 인코딩과 무관하게 출력 (실패 시 replace)."""
    try:
        print(text)
    except UnicodeEncodeError:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        sys.stdout.buffer.write((text + "\n").encode(enc, errors="replace"))
        sys.stdout.buffer.flush()


def print_banner() -> None:
    safe_print(BANNER)
