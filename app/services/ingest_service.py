import hashlib
import logging
import os
import re

from app.utils.embedder import embed_texts
from app.utils.loader import SUPPORTED_SUFFIXES, load_document
from app.utils.qdrant_client import delete_by_source, upsert_chunks
from app.utils.splitter import split_segments

logger = logging.getLogger(__name__)

# 落盘文件名形如 `sha256(内容)[:16] + 扩展名`
HASH_NAME_RE = re.compile(r"^[0-9a-f]{16}$")


def ingest_file(file_path: str, original_name: str | None = None) -> int:
    """单文件入库：加载 → 切分 → 向量化 → 写入。

    返回写入的 chunk 数。
    """
    segments = load_document(file_path)
    if original_name:
        for seg in segments:
            seg["metadata"]["original_name"] = original_name
    chunks = split_segments(segments)
    if not chunks:
        return 0

    vectors = embed_texts([c["text"] for c in chunks])
    return upsert_chunks(chunks, vectors)


def ingest_directory(dir_path: str) -> dict:
    """目录批量入库。返回统计信息。"""
    if not os.path.isdir(dir_path):
        raise FileNotFoundError(f"目录不存在：{dir_path}")

    files = 0
    total_chunks = 0
    stale_sources: list[str] = []
    for filename in sorted(os.listdir(dir_path)):
        filepath = os.path.join(dir_path, filename)
        if not os.path.isfile(filepath):
            continue
        if os.path.splitext(filename)[1].lower() not in SUPPORTED_SUFFIXES:
            continue

        # 处理"文件名本该是内容哈希、内容却变了"的陈旧文件（手动替换过文件才会出现）
        ingest_path, stale_source = _reconcile_stale_hash_name(filepath)
        if stale_source:
            stale_sources.append(stale_source)
        if ingest_path is None:
            continue

        n = ingest_file(ingest_path)
        logger.info("已入库 %s：%d 个 chunk", os.path.basename(ingest_path), n)
        files += 1
        total_chunks += n

    # 新版本都写完了再清理旧版本的向量：先写后删，中途失败也不会丢数据
    purged_points = 0
    for src in stale_sources:
        purged_points += delete_by_source(src)

    return {"files": files, "chunks": total_chunks, "purged_points": purged_points}


def _content_hash(path: str) -> str:
    """按块算内容哈希，规则与上传接口的命名一致：sha256 前 16 位十六进制。"""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()[:16]


def _reconcile_stale_hash_name(filepath: str) -> tuple[str | None, str | None]:
    """文件名是内容哈希、内容却变了时，改名成新哈希名并返回旧的 source 供清理。

    返回 `(要入库的路径 或 None, 需要清理的旧 source 或 None)`：
    文件名正常 → `(原路径, None)`；已改名 → `(新路径, 旧路径)`；
    正确哈希名的文件已存在 → 删除本文件并返回 `(None, 旧路径)`。
    """
    directory, filename = os.path.split(filepath)
    stem, ext = os.path.splitext(filename)
    if not HASH_NAME_RE.match(stem):
        return filepath, None

    actual = _content_hash(filepath)
    if actual == stem:
        return filepath, None

    target = os.path.join(directory, f"{actual}{ext}")
    if os.path.exists(target):
        os.remove(filepath)
        logger.warning("内容重复的陈旧文件已删除：%s（正确文件名为 %s）", filepath, target)
        return None, filepath

    os.replace(filepath, target)
    logger.warning("文件名与内容不符，已改名：%s -> %s（旧向量随后清理）", filepath, target)
    return target, filepath
