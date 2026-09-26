import json

import redis

from app.config import settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    """获取 Redis 客户端单例。"""
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            protocol=2,  # 兼容旧版 Redis
        )
    return _client


def get_history(session_id: str, max_turns: int = 6) -> list[dict]:
    """读取会话历史，最多返回最近 max_turns 轮（user+assistant 成对）。"""
    r = get_redis()
    key = f"chat:history:{session_id}"
    raw = r.lrange(key, -max_turns * 2, -1)
    return [json.loads(item) for item in raw]


def append_message(session_id: str, role: str, content: str) -> None:
    """追加一条消息到会话历史。"""
    r = get_redis()
    key = f"chat:history:{session_id}"
    r.rpush(key, json.dumps({"role": role, "content": content}, ensure_ascii=False))
    r.expire(key, settings.SESSION_EXPIRE_SECONDS)  # 24 小时过期


def clear_history(session_id: str) -> int:
    """清空会话历史，返回删除条数。"""
    r = get_redis()
    return r.delete(f"chat:history:{session_id}")
