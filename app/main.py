from fastapi import FastAPI

from app.config import settings
from app.routers.documents import router as documents_router
from app.routers.qa import router as qa_router
from app.utils.embedder import embed_query
from app.utils.qdrant_client import collection_info, ensure_collection

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
