import os

from app.config import settings

# 必须在导入 sentence_transformers(huggingface_hub) 之前设置：
# huggingface_hub 在 import 时就会读取 HF_ENDPOINT 并固化到 constants.ENDPOINT，
# 放在 import 之后设置是无效的。
# app.config 里的 load_dotenv() 不会覆盖已存在的环境变量，
# 所以先让 .env 的值生效，这里只作为 .env 未配置时的兜底。
os.environ.setdefault("HF_ENDPOINT", "https://huggingface.co")

from sentence_transformers import SentenceTransformer

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
