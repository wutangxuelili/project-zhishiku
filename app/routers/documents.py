import hashlib
import os
import shutil  # noqa: F401
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.services.ingest_service import ingest_file
from app.utils.loader import SUPPORTED_SUFFIXES
from app.utils.qdrant_client import delete_by_source, list_sources

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):  # noqa: B008
    """上传文档并入库。

    返回：文件名、保存路径、入库 chunk 数。
    """
    # 1. 校验扩展名
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail=f"仅支持 {', '.join(SUPPORTED_SUFFIXES)} 文件",
        )

    # 2. 确保上传目录存在
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()[:16]
    unique_name = f"{file_hash}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, unique_name)

    if os.path.exists(file_path):
        return {
            "message": "文件已存在，内容未变更",
            "filename": unique_name,
            "chunks": 0,
        }
    with open(file_path, "wb") as f:  # noqa: ASYNC230
        f.write(content)

    try:
        chunk_count = ingest_file(file_path, original_name=file.filename)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"入库失败：{e}")

    return {
        "message": "上传并入库成功",
        "filename": unique_name,
        "original_name": file.filename,
        "chunks": chunk_count,
    }


@router.get("/list")
def list_documents():
    """列出已入库的所有文档来源。"""
    return {"documents": list_sources()}


from pydantic import BaseModel


class DeleteRequest(BaseModel):
    source: str


@router.post("/delete")
def delete_document(request: DeleteRequest):
    """按 source 删除文档及其所有 chunk，同时删除本地文件。"""
    # 1. 删除 Qdrant 数据
    deleted = delete_by_source(request.source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"未找到来源：{request.source}")

    # 2. 安全删除本地文件
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    source_path = Path(request.source).resolve()

    # 只有当文件确实位于上传目录内，才删除
    if upload_dir in source_path.parents and source_path.is_file():
        source_path.unlink()

    return {
        "message": "删除成功",
        "source": request.source,
        "deleted_chunks": deleted,
    }
