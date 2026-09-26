"""批量入库脚本：把任意目录下的文件统一入库。

流程：扫描源目录 → 拷贝到 documents/（哈希命名）→ 入库（带 original_name）。
"""

import hashlib
import os
import shutil

from app.config import settings
from app.services.ingest_service import ingest_file
from app.utils.loader import SUPPORTED_SUFFIXES
from app.utils.qdrant_client import collection_info

SOURCE_DIR = "test_docs"  # 你要扫描的源目录


def main() -> None:
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    files = 0
    total_chunks = 0
    for filename in sorted(os.listdir(SOURCE_DIR)):
        src_path = os.path.join(SOURCE_DIR, filename)
        if not os.path.isfile(src_path):
            continue
        ext = os.path.splitext(filename)[1].lower()
        if ext not in SUPPORTED_SUFFIXES:
            continue

        # 读内容算哈希
        with open(src_path, "rb") as f:
            content = f.read()
        file_hash = hashlib.sha256(content).hexdigest()[:16]
        dst_name = f"{file_hash}{ext}"
        dst_path = os.path.join(settings.UPLOAD_DIR, dst_name)

        # 拷贝到 documents/
        if not os.path.exists(dst_path):
            shutil.copyfile(src_path, dst_path)

        # 入库
        n = ingest_file(dst_path, original_name=filename)
        print(f"  [ok] {filename} -> {dst_name}: {n} chunks")
        files += 1
        total_chunks += n

    print(f"\n入库完成：{files} 个文件，{total_chunks} 个 chunk")
    print("Qdrant 状态：", collection_info())


if __name__ == "__main__":
    main()
