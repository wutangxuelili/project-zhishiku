from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

# 单个 chunk 的目标字符数
CHUNK_SIZE = 400
# 相邻 chunk 的重叠字符数
CHUNK_OVERLAP = 50
# Markdown 标题层级 → metadata 键名
MARKDOWN_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def split_segments(segments: list[dict]) -> list[dict]:
    """把加载器输出的 segments 切成 chunks。

    输入: [{"text": str, "metadata": dict}, ...]
    输出: [{"text": str, "metadata": dict}, ...]
    """
    chunks = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue

        meta = dict(seg.get("metadata") or {})
        is_markdown = meta.get("type") == "md"

        for doc in _split_text(text, meta, is_markdown):
            chunks.append(
                {
                    "text": doc.page_content,
                    "metadata": dict(doc.metadata),
                }
            )
    return chunks


def _split_text(text: str, meta: dict, is_markdown: bool) -> list[Document]:
    """根据格式选择切分策略。"""
    if is_markdown:
        return _split_markdown(text, meta)
    return _split_recursive(text, meta)


def _split_markdown(text: str, meta: dict) -> list[Document]:
    """Markdown 两段式切分：先按标题，再按长度。"""
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MARKDOWN_HEADERS,
        strip_headers=False,
    )
    recursive = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )

    header_docs = header_splitter.split_text(text)
    result: list[Document] = []
    for doc in header_docs:
        merged = {**meta, **doc.metadata}
        result.extend(
            recursive.create_documents([doc.page_content], metadatas=[merged])
        )
    return result


def _split_recursive(text: str, meta: dict) -> list[Document]:
    """通用递归切分。"""
    recursive = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        add_start_index=True,
    )
    return recursive.create_documents([text], metadatas=[meta])
