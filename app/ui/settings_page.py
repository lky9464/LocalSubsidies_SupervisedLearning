"""설정 — data_root·ops.sqlite·분할 기본값."""

from __future__ import annotations

import streamlit as st
import yaml

from app.ui.common import get_cfg
from src.io.config import PROJECT_ROOT, get_data_root
from src.ops_db.db import get_ops_db_path, init_db


def render() -> None:
    cfg = get_cfg()
    st.title("설정")
    st.caption("경로·기본 분할은 여기와 YAML에서 관리합니다. 대시보드에는 경로를 표시하지 않습니다.")

    data_root = get_data_root(cfg)
    db_path = get_ops_db_path(cfg)
    st.subheader("경로")
    st.code(f"data_root = {data_root}\nops.sqlite = {db_path}")

    local_path = PROJECT_ROOT / "configs" / "local.yaml"
    example = PROJECT_ROOT / "configs" / "local.yaml.example"
    st.write(f"편집 파일: `{local_path}` (없으면 example 참고)")

    current_root = str(data_root)
    new_root = st.text_input("data_root 경로", value=current_root)
    if st.button("local.yaml에 data_root 저장"):
        payload: dict = {}
        if local_path.exists():
            with open(local_path, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        elif example.exists():
            with open(example, encoding="utf-8") as f:
                payload = yaml.safe_load(f) or {}
        payload["data_root"] = new_root
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
        st.success("저장됨. RunWeb.bat 을 재시작하면 반영됩니다.")
        get_cfg.clear()

    st.subheader("분할 기본값 (default.yaml)")
    st.json(cfg.get("split", {}))
    st.subheader("알고리즘")
    st.write(", ".join(cfg.get("algorithms") or []))

    if st.button("운영 DB 초기화/확인"):
        init_db(cfg)
        st.success(f"준비됨: {db_path}")
