import logging
import os

from app.config import settings

# 必须在导入 sentence_transformers(huggingface_hub) 之前设置：
# huggingface_hub 在 import 时就会读取 HF_ENDPOINT 并固化到 constants.ENDPOINT，
# 放在 import 之后设置是无效的。
# app.config 里的 load_dotenv() 不会覆盖已存在的环境变量，
# 所以先让 .env 的值生效，这里只作为 .env 未配置时的兜底。
os.environ.setdefault("HF_ENDPOINT", "https://huggingface.co")

from sentence_transformers import SentenceTransformer  # noqa: E402

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def _load_model() -> SentenceTransformer:
    """优先用本地缓存加载模型，本地没有权重时才联网下载。"""
    model_name = settings.EMBEDDING_MODEL

    try:
        model = SentenceTransformer(model_name, local_files_only=True)
        logger.info("向量模型已从本地缓存直接加载：%s", model_name)
        return model
    except Exception as e:  # noqa: BLE001
        if os.getenv("HF_HUB_OFFLINE", "").strip().lower() in {"1", "true", "yes"}:
            raise RuntimeError(
                f"HF_HUB_OFFLINE 已开启，但本地没有可用的模型缓存：{model_name}。"
                "请先在联网环境下载该模型，或把 .env 里的 HF_HUB_OFFLINE 设为 0。"
            ) from e
        logger.warning("本地无可用缓存，改为联网下载 %s：%s", model_name, e)

    return SentenceTransformer(model_name)


def get_embedding_model() -> SentenceTransformer:
    """返回嵌入模型(可选目前为BGE)"""
    global _model
    if _model is None:
        logger.info("正在加载向量模型：%s", settings.EMBEDDING_MODEL)
        _model = _load_model()
        logger.info("模型加载完成，维度：%s", settings.EMBEDDING_DIM)
    return _model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量向量化，就是把传入的文本先转向量然后再转列表返回 list[list[float]]。"""
    if not texts:
        return []
    return get_embedding_model().encode(texts).tolist()


def embed_query(text: str) -> list[float]:
    """单条查询向量化,返回 list[float]"""
    return embed_texts([text])[0]
