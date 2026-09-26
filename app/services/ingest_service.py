import os

from app.utils.embedder import embed_texts
from app.utils.loader import SUPPORTED_SUFFIXES, load_document
from app.utils.qdrant_client import upsert_chunks
from app.utils.splitter import split_segments


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
    for filename in sorted(os.listdir(dir_path)):
        filepath = os.path.join(dir_path, filename)
        if not os.path.isfile(filepath):
            continue
        if os.path.splitext(filename)[1].lower() not in SUPPORTED_SUFFIXES:
            continue
        n = ingest_file(filepath)
        print(f"  [ok] {filename}: {n} chunks")
        files += 1
        total_chunks += n

    return {"files": files, "chunks": total_chunks}
