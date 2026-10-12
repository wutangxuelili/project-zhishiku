import os

from dotenv import load_dotenv

load_dotenv()
# 试用方法为from app.config import settings


class Settings:
    """集中管理所有配置，从环境变量读取。"""

    # LLM
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    QWEN_BASE_URL: str = os.getenv(
        "QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-flash")
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
    # Qdrant
    QDRANT_HOST: str = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT: int = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "kb_qa")

    # Embedding
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
    EMBEDDING_DIM: int = int(os.getenv("EMBEDDING_DIM", "512"))
    # HuggingFace 端点：模型本地无缓存时从这里下载
    HF_ENDPOINT: str = os.getenv("HF_ENDPOINT", "https://huggingface.co")

    # 检索
    RETRIEVAL_CANDIDATES: int = int(os.getenv("RETRIEVAL_CANDIDATES", "15"))
    RERANK_CANDIDATES: int = int(os.getenv("RERANK_CANDIDATES", "10"))
    TOP_K: int = int(os.getenv("TOP_K", "3"))
    # 上传
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "documents")
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    # 会话过期时间（秒）
    SESSION_EXPIRE_SECONDS: int = int(os.getenv("SESSION_EXPIRE_SECONDS", "86400"))


settings = Settings()
