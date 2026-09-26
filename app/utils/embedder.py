import os

from sentence_transformers import SentenceTransformer

from app.config import settings

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 确保镜像在导入前生效

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """返回嵌入模型(可选目前为BGE)"""
    global _model
    if _model is None:
        print(f"[Embedding] 正在加载模型：{settings.EMBEDDING_MODEL}")
        _model = SentenceTransformer(settings.EMBEDDING_MODEL)
        print(f"[Embedding] 模型加载完成，维度：{settings.EMBEDDING_DIM}")
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，就是把传入的文本先转向量然后再转列表返回 list[list[float]]。"""
    if not texts:
        return []
    return get_embedding_model().encode(texts).tolist()


def embed_query(text: str) -> list[float]:
    """单条查询向量化,返回 list[float]"""
    return embed_texts([text])[0]
