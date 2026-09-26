from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
    """根据配置返回 LLM 客户端单例。"""
    global _client
    if _client is None:
        if settings.LLM_PROVIDER == "qwen":
            base_url = settings.QWEN_BASE_URL
            api_key = settings.DASHSCOPE_API_KEY
        else:
            base_url = settings.LLM_BASE_URL
            api_key = settings.LLM_API_KEY

        _client = OpenAI(base_url=base_url, api_key=api_key, timeout=60.0)
        print(f"[LLM] provider={settings.LLM_PROVIDER}, base_url={base_url}")
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
