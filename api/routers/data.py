"""Raw data registration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.deps import get_cfg, get_repo
from api.services.data import save_upload_files, unlink_registry_rows

router = APIRouter(prefix="/api/data", tags=["data"])


class SelectionBody(BaseModel):
    ids: list[int] = Field(default_factory=list)


_META_KEYS = (
    "id",
    "registered_at",
    "filename",
    "rel_path",
    "row_count",
    "note",
    "dataset_kind",
    "selected",
)


def _slim_items(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows:
        item = {k: r.get(k) for k in _META_KEYS}
        item["selected"] = bool(int(r.get("selected") or 0))
        out.append(item)
    return out


@router.get("/raw")
def list_train_raw(repo=Depends(get_repo)) -> dict:
    return {"items": _slim_items(repo.list_raw_registry(dataset_kind="train"))}


@router.get("/raw-inference")
def list_infer_raw(repo=Depends(get_repo)) -> dict:
    return {"items": _slim_items(repo.list_raw_registry(dataset_kind="inference"))}


@router.put("/raw/selection")
def put_train_selection(body: SelectionBody, repo=Depends(get_repo)) -> dict:
    n = repo.set_raw_selection(body.ids, dataset_kind="train")
    return {
        "ok": True,
        "selected_count": n,
        "rel_paths": repo.list_selected_rel_paths(dataset_kind="train"),
    }


@router.put("/raw-inference/selection")
def put_infer_selection(body: SelectionBody, repo=Depends(get_repo)) -> dict:
    n = repo.set_raw_selection(body.ids, dataset_kind="inference")
    return {
        "ok": True,
        "selected_count": n,
        "rel_paths": repo.list_selected_rel_paths(dataset_kind="inference"),
    }


@router.post("/raw")
async def upload_train_raw(
    files: list[UploadFile] = File(...),
    confirm_add: bool = False,
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
) -> dict:
    return await _upload(cfg, repo, files, dataset_kind="train", confirm_add=confirm_add)


@router.post("/raw-inference")
async def upload_infer_raw(
    files: list[UploadFile] = File(...),
    confirm_add: bool = False,
    cfg=Depends(get_cfg),
    repo=Depends(get_repo),
) -> dict:
    return await _upload(
        cfg, repo, files, dataset_kind="inference", confirm_add=confirm_add
    )


async def _upload(cfg, repo, files, *, dataset_kind: str, confirm_add: bool) -> dict:
    if not files:
        raise HTTPException(400, "파일이 없습니다.")
    existing = repo.count_raw_registry(dataset_kind=dataset_kind)
    if existing > 0 and not confirm_add:
        return {
            "needs_confirm": True,
            "message": (
                "이미 등록된 데이터가 있습니다. 풀에 추가 등록하시겠습니까? "
                "(학습/추론에 쓸 파일은 목록에서 선택한 뒤 「선택 저장」하세요.)"
            ),
        }
    pairs: list[tuple[str, bytes]] = []
    for uf in files:
        data = await uf.read()
        pairs.append((uf.filename or "upload.csv", data))
    try:
        n = save_upload_files(cfg, repo, pairs, dataset_kind=dataset_kind)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"saved": n, "needs_confirm": False}


@router.delete("/raw")
def delete_train_raw(ids: str, cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not id_list:
        raise HTTPException(400, "삭제할 id가 없습니다.")
    deleted = repo.delete_raw_registry_ids(id_list, dataset_kind="train")
    unlink_registry_rows(cfg, deleted)
    return {"deleted": len(deleted)}


@router.delete("/raw-inference")
def delete_infer_raw(ids: str, cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    if not id_list:
        raise HTTPException(400, "삭제할 id가 없습니다.")
    deleted = repo.delete_raw_registry_ids(id_list, dataset_kind="inference")
    unlink_registry_rows(cfg, deleted)
    return {"deleted": len(deleted)}


@router.delete("/raw/all")
def clear_train_raw(cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    deleted = repo.clear_raw_registry(dataset_kind="train")
    unlink_registry_rows(cfg, deleted)
    return {"deleted": len(deleted)}


@router.delete("/raw-inference/all")
def clear_infer_raw(cfg=Depends(get_cfg), repo=Depends(get_repo)) -> dict:
    deleted = repo.clear_raw_registry(dataset_kind="inference")
    unlink_registry_rows(cfg, deleted)
    return {"deleted": len(deleted)}
