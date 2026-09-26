import os

import pdfplumber

# 支持的扩展名
SUPPORTED_SUFFIXES = (".pdf", ".md", ".txt")


def load_document(file_path: str) -> list[dict]:
    """加载单个文件，返回 [{"text": str, "metadata": dict}, ...]。

    - PDF：按页返回，每页一个 segment，metadata 带 page。
    - Markdown / TXT：整个文件作为一个 segment 返回。"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_SUFFIXES:
        raise ValueError(f"不支持的文件类型:{ext}")

    if ext == ".pdf":
        return _load_pdf(file_path)
    else:
        return _load_text(file_path, ext)


def _load_pdf(file_path: str) -> list[dict]:
    """按页提取 PDF 文本。"""
    segments = []
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue
            segments.append(
                {
                    "text": text,
                    "metadata": {
                        "source": file_path,
                        "type": "pdf",
                        "page": page_num,
                    },
                }
            )
    return segments


def _load_text(file_path: str, ext: str) -> list[dict]:
    """读取 Markdown / TXT 文件。"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    if not content.strip():
        return []
    return [
        {"text": content, "metadata": {"source": file_path, "type": ext.lstrip(".")}}
    ]
