import hashlib
import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.services.ingest_service import ingest_directory, ingest_file
from app.utils.loader import SUPPORTED_SUFFIXES
from app.utils.qdrant_client import (
    delete_by_source,
    list_sources,
    replace_same_name_document,
)

router = APIRouter(prefix="/documents", tags=["Documents"])


def _remove_local_file(source: str) -> bool:
    """删除上传目录内的文件；路径不在上传目录内则拒绝（防目录穿越）。"""
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    source_path = Path(source).resolve()
    if upload_dir in source_path.parents and source_path.is_file():
        source_path.unlink()
        return True
    return False


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):  # noqa: B008
    """上传文档并入库。

    返回：文件名、保存路径、入库 chunk 数。
    """
    # 1. 校验扩展名。
    #    file.filename 的类型是 str | None，客户端不带文件名时会是 None，
    #    直接丢给 os.path.splitext 会抛 TypeError 变成 500，所以先兜底成空串。
    filename = file.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if not filename or ext not in SUPPORTED_SUFFIXES:
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

    existed = os.path.exists(file_path)
    if not existed:
        with open(file_path, "wb") as f:  # noqa: ASYNC230
            f.write(content)

    # 3. 入库。
    #    注意：不能因为磁盘上已经有同名文件就跳过入库。Qdrant 的数据可能被清空或
    #    重建（换机器、删掉 volume、改了容器编排），此时只有重新入库，文档才会重新
    #    出现在"已入库文档"里。所以这里以 Qdrant 为准，一律执行入库；
    #    upsert_chunks 用 (source, text) 的稳定哈希当 id，重复入库是幂等的，不会产生重复数据。
    try:
        chunk_count = ingest_file(file_path, original_name=filename)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"入库失败：{e}")

    # 4. 同名替换：文档改版时，清掉旧版本的向量和旧文件（先入库新的，成功后再删旧的）
    replaced = replace_same_name_document(filename, keep_source=file_path)
    removed_files = sum(1 for src in replaced["removed_sources"] if _remove_local_file(src))

    return {
        "message": "文件已存在，已重新入库" if existed else "上传并入库成功",
        "filename": unique_name,
        "original_name": filename,
        "chunks": chunk_count,
        "replaced_chunks": replaced["deleted_points"],
        "removed_old_files": removed_files,
    }


@router.post("/reindex")
def reindex_documents():
    """重新扫描上传目录，把目录里的文档（重新）入库。

    用于 Qdrant 数据被清空/重建后，一键恢复已有文档的索引。
    """
    try:
        stats = ingest_directory(settings.UPLOAD_DIR)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"重建索引失败：{e}")

    return {"message": f"已重新入库 {stats['files']} 个文件", **stats}


@router.get("/list")
def list_documents():
    """列出已入库的所有文档来源。"""
    return {"documents": list_sources()}


class DeleteRequest(BaseModel):
    source: str = Field(min_length=1, max_length=512)


@router.post("/delete")
def delete_document(request: DeleteRequest):
    """按 source 删除文档及其所有 chunk，同时删除本地文件。"""
    # 1. 删除 Qdrant 数据
    deleted = delete_by_source(request.source)
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"未找到来源：{request.source}")

    # 2. 安全删除本地文件
    _remove_local_file(request.source)

    return {
        "message": "删除成功",
        "source": request.source,
        "deleted_chunks": deleted,
    }
