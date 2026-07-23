"""로컬 운영 SQLite (raw 미포함). 위치: {data_root}/ops/ops.sqlite"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    operator TEXT,
    work_content TEXT,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS run_steps (
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT,
    ended_at TEXT,
    message TEXT,
    log_path TEXT,
    PRIMARY KEY (run_id, step_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS model_ranking (
    run_id TEXT NOT NULL,
    rank INTEGER NOT NULL,
    algo TEXT NOT NULL,
    role TEXT NOT NULL,
    pr_auc REAL,
    roc_auc REAL,
    top1_lift REAL,
    f1 REAL,
    PRIMARY KEY (run_id, algo),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS eval_metrics (
    run_id TEXT NOT NULL,
    algo TEXT NOT NULL,
    metric_key TEXT NOT NULL,
    metric_value REAL,
    PRIMARY KEY (run_id, algo, metric_key),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS raw_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registered_at TEXT NOT NULL,
    filename TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    row_count INTEGER,
    file_sha256 TEXT,
    note TEXT,
    dataset_kind TEXT NOT NULL DEFAULT 'train',
    selected INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS raw_inference_registry (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registered_at TEXT NOT NULL,
    filename TEXT NOT NULL,
    rel_path TEXT NOT NULL,
    row_count INTEGER,
    file_sha256 TEXT,
    note TEXT,
    selected INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS ops_queue_rows (
    run_id TEXT NOT NULL,
    crtr_ym TEXT,
    pfm_biz_id TEXT,
    inst_id TEXT,
    biz_nm TEXT,
    inst_nm TEXT,
    sbat_amt TEXT,
    pyhwy_amt TEXT,
    score_primary REAL,
    score_aux REAL,
    ops_grade TEXT,
    cross_check TEXT,
    grade_aux TEXT,
    priority INTEGER,
    pred_label TEXT,
    actual_label TEXT,
    PRIMARY KEY (run_id, crtr_ym, pfm_biz_id, inst_id),
    FOREIGN KEY (run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_ops_queue_grade
    ON ops_queue_rows(run_id, ops_grade);
"""


def get_ops_db_path(cfg: dict[str, Any]) -> Path:
    from src.io.config import get_data_root

    path = get_data_root(cfg) / "ops" / "ops.sqlite"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def connect(cfg: dict[str, Any]) -> sqlite3.Connection:
    """짧은 busy_timeout — UI 스레드가 DB 락에 오래 걸리지 않도록."""
    db_path = get_ops_db_path(cfg)
    conn = sqlite3.connect(str(db_path), timeout=5.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
    except sqlite3.Error:
        pass
    return conn


def init_db(cfg: dict[str, Any]) -> Path:
    """스키마 생성. raw 내용 테이블은 의도적으로 없음 (메타만)."""
    path = get_ops_db_path(cfg)
    with connect(cfg) as conn:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        conn.commit()
    return path


def _migrate(conn: sqlite3.Connection) -> None:
    """기존 DB에 컬럼/테이블 보강."""
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(raw_registry)").fetchall()
    }
    if "dataset_kind" not in cols:
        conn.execute(
            "ALTER TABLE raw_registry ADD COLUMN dataset_kind TEXT NOT NULL DEFAULT 'train'"
        )
    # 기존 등록분은 즉시 사용 가능하도록 selected=1
    if "selected" not in cols:
        conn.execute(
            "ALTER TABLE raw_registry ADD COLUMN selected INTEGER NOT NULL DEFAULT 1"
        )

    infer_cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(raw_inference_registry)").fetchall()
    }
    if infer_cols and "selected" not in infer_cols:
        conn.execute(
            "ALTER TABLE raw_inference_registry ADD COLUMN selected INTEGER NOT NULL DEFAULT 1"
        )

    ops_cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(ops_queue_rows)").fetchall()
    }
    if ops_cols and "priority" not in ops_cols:
        conn.execute("ALTER TABLE ops_queue_rows ADD COLUMN priority INTEGER")

    run_cols = {
        r[1] for r in conn.execute("PRAGMA table_info(runs)").fetchall()
    }
    if run_cols and "operator" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN operator TEXT")
    if run_cols and "work_content" not in run_cols:
        conn.execute("ALTER TABLE runs ADD COLUMN work_content TEXT")

    # Execution 스냅샷 기능 철회 — 잔여 테이블 제거
    conn.execute("DROP TABLE IF EXISTS executions")

    _migrate_model_ranking_pk(conn)
    _migrate_model_ranking_metrics(conn)


def _migrate_model_ranking_metrics(conn: sqlite3.Connection) -> None:
    """model_ranking에 top-k 부가 지표 컬럼 추가."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(model_ranking)").fetchall()}
    if not cols:
        return
    for col in (
        "top1_precision",
        "top1_recall",
        "top5_lift",
        "top5_precision",
        "top5_recall",
    ):
        if col not in cols:
            conn.execute(f"ALTER TABLE model_ranking ADD COLUMN {col} REAL")


def _migrate_model_ranking_pk(conn: sqlite3.Connection) -> None:
    """동순 rank(1,1,3) 허용: PK (run_id,rank) → (run_id,algo)."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='model_ranking'"
    ).fetchone()
    if not row or not row[0]:
        return
    ddl = row[0]
    if "PRIMARY KEY (run_id, algo)" in ddl.replace("\n", " "):
        return
    conn.executescript(
        """
        CREATE TABLE model_ranking_new (
            run_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            algo TEXT NOT NULL,
            role TEXT NOT NULL,
            pr_auc REAL,
            roc_auc REAL,
            top1_lift REAL,
            f1 REAL,
            PRIMARY KEY (run_id, algo),
            FOREIGN KEY (run_id) REFERENCES runs(run_id)
        );
        INSERT INTO model_ranking_new(
            run_id, rank, algo, role, pr_auc, roc_auc, top1_lift, f1
        )
        SELECT run_id, rank, algo, role, pr_auc, roc_auc, top1_lift, f1
        FROM model_ranking;
        DROP TABLE model_ranking;
        ALTER TABLE model_ranking_new RENAME TO model_ranking;
        """
    )
