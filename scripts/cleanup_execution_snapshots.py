"""Execution 스냅샷 잔여물 정리 (로컬 전용).

제거:
  - ops.sqlite 의 executions 테이블
  - {data_root}/runs/*/executions/ 폴더

Cursor Agent는 실행하지 마세요. 사용자가 로컬에서 실행합니다.

  python scripts/cleanup_execution_snapshots.py
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.io.config import get_data_root, load_config  # noqa: E402
from src.ops_db.db import get_ops_db_path  # noqa: E402


def main() -> int:
    cfg = load_config()
    data_root = get_data_root(cfg)
    runs_dir = data_root / "runs"
    removed_dirs = 0

    if runs_dir.is_dir():
        for run_dir in runs_dir.iterdir():
            if not run_dir.is_dir():
                continue
            exec_dir = run_dir / "executions"
            if exec_dir.is_dir():
                shutil.rmtree(exec_dir, ignore_errors=True)
                removed_dirs += 1
                print(f"[cleanup] removed: runs/{run_dir.name}/executions/")

    db_path = get_ops_db_path(cfg)
    if db_path.is_file():
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("DROP TABLE IF EXISTS executions")
            conn.commit()
            print("[cleanup] DROP TABLE IF EXISTS executions")
        finally:
            conn.close()
    else:
        print(f"[cleanup] ops DB 없음 (건너뜀): {db_path.name}")

    print(f"[cleanup] done. executions folders removed={removed_dirs}")
    print("Restart web (RestartWeb.bat) after cleanup.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
