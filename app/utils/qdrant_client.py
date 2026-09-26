import hashlib

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.config import settings

_client: QdrantClient | None = None


def get_qdrant() -> QdrantClient:
    """返回Qdrant客户端"""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
    return _client


def ensure_collection() -> None:
    """无返回值,集合不存在时则创建新集合(存在则不动)"""
    client = get_qdrant()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.EMBEDDING_DIM,
                distance=Distance.COSINE,
            ),
        )
        print(f"[Qdrant]已创建集合{settings.QDRANT_COLLECTION}")
    else:
        print(f"[Qdrant]集合已存在:{settings.QDRANT_COLLECTION}")


def collection_info() -> dict:
    """返回集合的基本信息 indexed_vectors_count为集合中已存储的向量数量 points_count为数据点数量,用于健康检查"""
    client = get_qdrant()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        return {"exists": False}
    info = client.get_collection(settings.QDRANT_COLLECTION)
    return {
        "exists": True,
        "indexed_vectors_count": info.indexed_vectors_count,
        "points_count": info.points_count,
        "status": str(info.status),
    }


def make_point_id(source: str, text: str) -> int:
    """由 (来源, 内容) 生成稳定 id。

    不用 Python 内置 hash()：字符串 hash 每个进程都会变，
    重复入库会产生重复点。
    """
    key = f"{source}::{text}".encode()
    return int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")


def upsert_chunks(chunks: list[dict], vectors: list[list[float]]) -> int:
    """把 chunk + 对应向量写入 Qdrant，返回写入条数len。

    :param chunks:  [{"text": str, "metadata": dict}, ...]
    :param vectors: 与 chunks 等长的向量列表
    """
    from qdrant_client.models import PointStruct

    if not chunks:
        return 0
    if len(chunks) != len(vectors):
        raise ValueError(f"chunks({len(chunks)}) 与 vectors({len(vectors)}) 数量不一致")

    ensure_collection()

    points = []
    for chunk, vec in zip(chunks, vectors):
        text = chunk["text"]
        meta = dict(chunk.get("metadata") or {})
        source = meta.get("source", "")
        points.append(
            PointStruct(
                id=make_point_id(source, text),
                vector=vec,
                payload={"text": text, **meta},
            )
        )

    get_qdrant().upsert(
        collection_name=settings.QDRANT_COLLECTION,
        points=points,
        wait=True,
    )
    return len(points)


def vector_search(query_vector: list[float], top_k: int = 3) -> list[dict]:
    """向量检索，返回 [{"text": ..., "metadata": ..., "score": ...}, ...]。"""
    client = get_qdrant()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        return []

    results = client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=query_vector,
        limit=top_k,
    )
    return [
        {
            "text": (hit.payload or {}).get("text", ""),
            "metadata": {k: v for k, v in (hit.payload or {}).items() if k != "text"},
            "score": hit.score,
        }
        for hit in results.points
    ]


def list_sources() -> list[dict]:
    """列出集合中所有文档来源及各自的 chunk 数。"""
    client = get_qdrant()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        return []

    counts: dict[str, int] = {}
    originals: dict[str, str] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=settings.QDRANT_COLLECTION,
            limit=256,
            with_payload=True,
            with_vectors=False,
            offset=offset,
        )
        for p in points:
            payload = p.payload or {}
            source = payload.get("source", "unknown")
            counts[source] = counts.get(source, 0) + 1
            # 记录原始名（同一个 source 所有 chunk 的 original_name 相同）
            if payload.get("original_name"):
                originals[source] = payload["original_name"]
        if offset is None:
            break

    return [
        {
            "source": src,
            "chunks": cnt,
            "original_name": originals.get(src),
        }
        for src, cnt in sorted(counts.items())
    ]


def delete_by_source(source: str) -> int:
    """删除指定来源的所有 chunk，返回删除数量。"""
    from qdrant_client.models import FieldCondition, Filter, MatchValue

    client = get_qdrant()
    if not client.collection_exists(settings.QDRANT_COLLECTION):
        return 0

    # 先统计要删除的数量
    count_result = client.count(
        collection_name=settings.QDRANT_COLLECTION,
        count_filter=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source))]
        ),
        exact=True,
    )
    to_delete = count_result.count
    if to_delete == 0:
        return 0

    # 执行删除
    client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=Filter(
            must=[FieldCondition(key="source", match=MatchValue(value=source))]
        ),
        wait=True,
    )
    return to_delete
