import logging

from fastapi import FastAPI

from app.config import settings
from app.routers.documents import router as documents_router
from app.routers.qa import router as qa_router
from app.utils.embedder import embed_query
from app.utils.qdrant_client import collection_info, ensure_collection

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# 第三方库的 INFO 日志太吵（httpx 会把每个请求都打出来），压到 WARNING。
# 注意本项目装的是 httpx2 / httpcore2，两个都列上。
for _noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "urllib3", "filelock"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

app = FastAPI(
    title="知识库问答系统",
    description="支持 PDF/Markdown 上传、向量检索、引用来源和多轮对话",
    version="0.1.0",
)

app.include_router(qa_router)
app.include_router(documents_router)


@app.on_event("startup")
def on_startup() -> None:
    """确保Qdrant集合存在"""
    ensure_collection()


@app.get("/health")
def health_check():
    """健康检查接口"""
    test_vec = embed_query("健康检查")
    return {
        "status": "ok",
        "qdrant": collection_info(),
        "embedding": {"model": settings.EMBEDDING_MODEL, "dim": len(test_vec)},
    }
