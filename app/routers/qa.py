from fastapi import APIRouter
from pydantic import BaseModel

from app.services.qa_service import answer_question

router = APIRouter(prefix="/qa", tags=["QA"])


class AskRequest(BaseModel):
    question: str
    top_k: int = 3
    session_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    citations: dict


class ClearRequest(BaseModel):
    session_id: str


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
