from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.config import settings
from app.services.qa_service import answer_question

router = APIRouter(prefix="/qa", tags=["QA"])

# 单请求最多召回多少片段
TOP_K_MAX = 20

# .env 的 TOP_K 作为默认值，写超上限时按上限截断
DEFAULT_TOP_K = max(1, min(settings.TOP_K, TOP_K_MAX))

# session_id 会被拼进 Redis key，限制长度与字符集
SESSION_ID_PATTERN = r"^[A-Za-z0-9_.:-]{0,64}$"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=TOP_K_MAX)
    session_id: str | None = Field(
        default=None, max_length=64, pattern=SESSION_ID_PATTERN
    )


class AskResponse(BaseModel):
    answer: str
    citations: dict


class ClearRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64, pattern=SESSION_ID_PATTERN)


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest):
    """知识库问答接口。"""
    result = answer_question(
        request.question, top_k=request.top_k, session_id=request.session_id
    )
    return AskResponse(**result)


@router.post("/clear")
def clear(request: ClearRequest):
    """清空指定会话的 Redis 历史。"""
    from app.utils.redis_client import clear_history

    deleted = clear_history(request.session_id)
    return {"message": "已清空", "deleted": deleted}
