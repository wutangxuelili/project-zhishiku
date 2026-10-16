import logging

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_api_key() -> str:
    """返回当前 provider 对应的 API Key。"""
    if settings.LLM_PROVIDER == "qwen":
        return settings.DASHSCOPE_API_KEY
    return settings.LLM_API_KEY


def has_api_key() -> bool:
    """Key 是否已配置（`.env.example` 里的占位符算未配置）。"""
    key = get_api_key().strip()
    return bool(key) and not key.startswith("sk-请替换")


def get_llm_client() -> OpenAI:
    """根据配置返回 LLM 客户端单例。"""
    global _client
    if _client is None:
        base_url = (
            settings.QWEN_BASE_URL
            if settings.LLM_PROVIDER == "qwen"
            else settings.LLM_BASE_URL
        )
        _client = OpenAI(
            base_url=base_url,
            api_key=get_api_key(),
            timeout=60.0,
        )
        logger.info("LLM 客户端已初始化：provider=%s, base_url=%s", settings.LLM_PROVIDER, base_url)
    return _client


def get_model_name() -> str:
    """返回当前 provider 对应的模型名。"""
    if settings.LLM_PROVIDER == "qwen":
        return settings.QWEN_MODEL
    return settings.LLM_MODEL


def chat(messages: list[dict], temperature: float = 0.3) -> str:
    """调用 LLM，返回回复文本。"""
    client = get_llm_client()
    completion = client.chat.completions.create(
        model=get_model_name(),
        messages=messages,
        temperature=temperature,
    )
    return completion.choices[0].message.content
