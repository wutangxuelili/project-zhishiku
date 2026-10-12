import logging

from app.utils.embedder import embed_query
from app.utils.llm_client import chat
from app.utils.qdrant_client import vector_search
from app.utils.redis_client import append_message, get_history

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个知识库问答助手。请严格依据下方【上下文】回答用户问题。

规则：
1. 如果上下文中含有能回答问题的信息，就必须基于上下文作答，不要拒答。
2. 如果上下文与问题完全无关，回答“根据现有资料无法回答”。
3. 引用了【资料N】的内容，就在句末标注 [N]。
4. 不要编造上下文中不存在的信息。"""

NO_ANSWER = "根据现有资料无法回答。"


def answer_question(
    question: str,
    top_k: int = 3,
    session_id: str | None = None,
) -> dict:
    """完整问答流程：检索 → 拼上下文 → LLM 生成（含多轮历史）。"""
    # 1. 读取历史
    history = get_history(session_id) if session_id else []
    # 2. 检索
    search_query = rewrite_query(question, history)
    query_vec = embed_query(search_query)
    hits = vector_search(query_vec, top_k=top_k)
    logger.debug(
        "session=%s history_turns=%d query=%r hits=%s",
        session_id,
        len(history),
        search_query,
        [(h["metadata"].get("original_name"), h["metadata"].get("h2")) for h in hits],
    )
    # 3. 拼上下文
    if not hits:
        answer = NO_ANSWER
        citations = {}
    else:
        context_parts = [
            f"【资料{i}】\n{hit['text']}" for i, hit in enumerate(hits, start=1)
        ]
        context = "\n\n".join(context_parts)

        # 4. 组装 messages：system + 历史 + 当前问题
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append(
            {
                "role": "user",
                "content": f"上下文：\n{context}\n\n问题：{question}",
            }
        )

        answer = chat(messages, temperature=0.3)

        citations = {
            i: {
                "text": hit["text"],
                "source": hit["metadata"].get("source", ""),
                "original_name": hit["metadata"].get("original_name"),
                "page": hit["metadata"].get("page"),
                "score": hit["score"],
            }
            for i, hit in enumerate(hits, start=1)
        }

    # 5. 写入历史
    if session_id:
        append_message(session_id, "user", question)
        append_message(session_id, "assistant", answer)

    return {"answer": answer, "citations": citations}


def rewrite_query(question: str, history: list[dict]) -> str:
    """用 LLM 把追问改写成独立问题。"""
    if not history:
        return question  # 第一轮不用改写

    history_text = "\n".join(f"{m['role']}: {m['content'][:100]}" for m in history[-4:])
    prompt = f"""根据对话历史，把用户的最新问题改写成一个独立、完整的问题。
    要求：
    1. 不要改变原意。
    2. 如果问题已经完整，直接返回原问题。
    3. 只输出改写后的问题，不要任何解释。

    对话历史：
    {history_text}

    最新问题：{question}
    改写后的问题："""

    rewritten = chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
    )
    return rewritten.strip()
