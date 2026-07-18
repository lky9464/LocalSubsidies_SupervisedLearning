"""데이터 등록 — 학습/평가 raw + 추론 raw (메타만 DB)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import streamlit as st

from app.ui.common import get_cfg
from src.io.config import get_data_root, resolve_data_path
from src.ops_db.repository import OpsRepository


def render() -> None:
    cfg = get_cfg()
    repo = OpsRepository(cfg)
    st.title("데이터 등록")
    st.caption(
        "업로드는 로컬 data_root 하위 폴더에만 저장됩니다. "
        "DB에는 파일명·건수·해시 메타만 기록합니다 (raw 내용 ∉ DB)."
    )

    _section_upload(
        cfg,
        repo,
        title="학습·평가 raw 데이터",
        caption="TLS4902R 레이아웃 CSV(통상 8종). `data_root/raw` 에 저장됩니다.",
        target_dir=resolve_data_path(cfg, "raw"),
        rel_prefix="raw",
        dataset_kind="train",
        key_prefix="train",
    )

    st.divider()

    _section_upload(
        cfg,
        repo,
        title="추론 raw 데이터",
        caption=(
            "학습·평가와 동일한 CSV 레이아웃(8종)을 사용합니다. "
            "다만 `TAET_YN` 및 타겟 수정용 3개 컬럼"
            "(ISDP_RGSTR_YN / ISRC_DSCL_YN / PMBZ_CFMTN_YN)은 "
            "추론에서 사용하지 않으며, 값이 있어도 무시됩니다. "
            "저장 위치: `data_root/raw_inference`."
        ),
        target_dir=get_data_root(cfg) / "raw_inference",
        rel_prefix="raw_inference",
        dataset_kind="inference",
        key_prefix="infer",
    )


def _section_upload(
    cfg: dict,
    repo: OpsRepository,
    *,
    title: str,
    caption: str,
    target_dir: Path,
    rel_prefix: str,
    dataset_kind: str,
    key_prefix: str,
) -> None:
    st.subheader(title)
    st.caption(caption)
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded = st.file_uploader(
        "CSV 업로드",
        type=["csv"],
        accept_multiple_files=True,
        key=f"{key_prefix}_uploader",
    )

    if uploaded and st.button("로컬에 저장", type="primary", key=f"{key_prefix}_save_btn"):
        existing = repo.count_raw_registry(dataset_kind=dataset_kind)
        if existing > 0:
            st.session_state[f"{key_prefix}_pending_files"] = [
                {"name": uf.name, "data": uf.getvalue()} for uf in uploaded
            ]
            st.session_state[f"{key_prefix}_confirm_add"] = True
            st.rerun()
        else:
            _save_files(cfg, repo, uploaded, target_dir, rel_prefix, dataset_kind)
            st.success(f"{len(uploaded)}개 파일 저장 및 메타 기록 완료")

    if st.session_state.get(f"{key_prefix}_confirm_add"):
        _confirm_add_dialog(cfg, repo, target_dir, rel_prefix, dataset_kind, key_prefix)

    st.markdown("##### 등록 메타 (DB)")
    reg = repo.list_raw_registry(dataset_kind=dataset_kind)
    if not reg:
        st.write("등록 메타 없음")
        return

    df = pd.DataFrame(reg)
    select_mode = st.session_state.get(f"{key_prefix}_select_mode", False)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("선택 삭제", key=f"{key_prefix}_sel_del"):
            st.session_state[f"{key_prefix}_select_mode"] = True
            st.rerun()
    with c2:
        if st.button("초기화(전체삭제)", key=f"{key_prefix}_clear"):
            st.session_state[f"{key_prefix}_confirm_clear"] = True
            st.rerun()
    with c3:
        if select_mode and st.button("선택 모드 취소", key=f"{key_prefix}_sel_cancel"):
            st.session_state[f"{key_prefix}_select_mode"] = False
            st.rerun()

    if st.session_state.get(f"{key_prefix}_confirm_clear"):
        _confirm_clear_dialog(cfg, repo, dataset_kind, key_prefix)

    if select_mode:
        edit = df.copy()
        edit.insert(0, "선택", False)
        edited = st.data_editor(
            edit,
            hide_index=True,
            use_container_width=True,
            key=f"{key_prefix}_editor",
            disabled=[c for c in edit.columns if c != "선택"],
            column_config={"선택": st.column_config.CheckboxColumn(required=False)},
        )
        if st.button("선택한 항목 삭제", type="primary", key=f"{key_prefix}_do_del"):
            ids = [
                int(r["id"])
                for _, r in edited.iterrows()
                if bool(r.get("선택")) and pd.notna(r.get("id"))
            ]
            if not ids:
                st.warning("삭제할 항목을 체크하세요.")
            else:
                _delete_meta_and_files(cfg, repo, ids, dataset_kind)
                st.session_state[f"{key_prefix}_select_mode"] = False
                st.success(f"{len(ids)}건 삭제")
                st.rerun()
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)


def _confirm_add_dialog(
    cfg: dict,
    repo: OpsRepository,
    target_dir: Path,
    rel_prefix: str,
    dataset_kind: str,
    key_prefix: str,
) -> None:
    pending = st.session_state.get(f"{key_prefix}_pending_files") or []

    @st.dialog("추가 등록 확인")
    def _dlg() -> None:
        st.warning(
            "이미 등록된 데이터가 있습니다. "
            "추가로 등록하시겠습니까? (기존 메타는 유지되고 파일이 더해집니다.)"
        )
        c1, c2 = st.columns(2)
        with c1:
            if st.button("등록", type="primary", key=f"{key_prefix}_dlg_ok"):
                class _UF:
                    def __init__(self, name: str, data: bytes) -> None:
                        self.name = name
                        self._data = data

                    def getvalue(self) -> bytes:
                        return self._data

                files = [_UF(p["name"], p["data"]) for p in pending]
                _save_files(cfg, repo, files, target_dir, rel_prefix, dataset_kind)
                st.session_state[f"{key_prefix}_confirm_add"] = False
                st.session_state[f"{key_prefix}_pending_files"] = None
                st.rerun()
        with c2:
            if st.button("취소", key=f"{key_prefix}_dlg_cancel"):
                st.session_state[f"{key_prefix}_confirm_add"] = False
                st.session_state[f"{key_prefix}_pending_files"] = None
                st.rerun()

    _dlg()


def _confirm_clear_dialog(
    cfg: dict, repo: OpsRepository, dataset_kind: str, key_prefix: str
) -> None:
    @st.dialog("전체 삭제 확인")
    def _dlg() -> None:
        st.error("등록 메타와 로컬 파일을 모두 삭제합니다. 정말 진행할까요?")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("삭제", type="primary", key=f"{key_prefix}_clear_ok"):
                rows = repo.clear_raw_registry(dataset_kind=dataset_kind)
                _unlink_rows(cfg, rows)
                st.session_state[f"{key_prefix}_confirm_clear"] = False
                st.rerun()
        with c2:
            if st.button("취소", key=f"{key_prefix}_clear_cancel"):
                st.session_state[f"{key_prefix}_confirm_clear"] = False
                st.rerun()

    _dlg()


def _save_files(
    cfg: dict,
    repo: OpsRepository,
    uploaded: list,
    target_dir: Path,
    rel_prefix: str,
    dataset_kind: str,
) -> None:
    for uf in uploaded:
        dest = target_dir / uf.name
        data = uf.getvalue()
        dest.write_bytes(data)
        try:
            text = data.decode(cfg.get("encoding", "EUC-KR"), errors="replace")
            row_count = max(0, text.count("\n") - 1)
        except Exception:  # noqa: BLE001
            row_count = None
        sha = hashlib.sha256(data).hexdigest()
        repo.register_raw_file(
            uf.name,
            f"{rel_prefix}/{uf.name}",
            row_count=row_count,
            file_sha256=sha,
            note="streamlit_upload",
            dataset_kind=dataset_kind,
        )


def _delete_meta_and_files(
    cfg: dict, repo: OpsRepository, ids: list[int], dataset_kind: str
) -> None:
    rows = repo.delete_raw_registry_ids(ids, dataset_kind=dataset_kind)
    _unlink_rows(cfg, rows)


def _unlink_rows(cfg: dict, rows: list[dict]) -> None:
    root = get_data_root(cfg)
    for r in rows:
        rel = r.get("rel_path") or ""
        path = root / rel if rel else None
        if path and path.is_file():
            try:
                path.unlink()
            except OSError:
                pass
