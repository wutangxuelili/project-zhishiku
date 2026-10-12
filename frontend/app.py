# 后端地址（可通过环境变量覆盖）
import os
import re
import uuid

import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")


@st.cache_data(ttl=5, show_spinner=False)
def fetch_documents() -> list[dict]:
    """获取已入库文档列表。

    Streamlit 每次交互都会重跑整个脚本，直接请求会导致"每问一句就多打一次接口"，
    这里用 5 秒缓存挡掉同一轮交互里的重复请求。
    """
    resp = requests.get(f"{BACKEND_URL}/documents/list", timeout=10)
    resp.raise_for_status()
    return resp.json().get("documents", [])


def invalidate_documents_cache() -> None:
    """入库 / 删除 / 重建索引之后调用，让下一次渲染立刻拿到最新列表。"""
    fetch_documents.clear()


def highlight_citations(answer: str) -> str:
    """把回答里的 [1]、[2] 换成带颜色的标记。"""
    # Streamlit markdown 支持 :color[文本] 语法
    return re.sub(r"\[(\d+)\]", r":blue[**[\1]**]", answer)


def render_citations(citations: dict) -> None:
    """用可折叠的卡片渲染引用。"""
    if not citations:
        return

    with st.expander(f"📖 查看引用来源（{len(citations)} 条）", expanded=False):
        for idx, cite in citations.items():
            source = cite.get("original_name") or cite.get("source", "未知来源")
            page = cite.get("page")
            page_info = f" · 第 {page} 页" if page else ""
            score = cite.get("score", 0)

            st.markdown(
                f"**:blue[[{idx}]]** `{source}`{page_info} · 相似度 `{score:.3f}`"
            )
            st.text(cite["text"][:400] + ("..." if len(cite["text"]) > 400 else ""))
            st.divider()


st.set_page_config(page_title="知识库问答", page_icon="📚", layout="wide")
st.title("📚 知识库问答系统")

# 初始化 session_id（页面刷新不丢，关闭标签页后重开是新会话）
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

# 初始化聊天历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 显示历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            st.markdown(highlight_citations(msg["content"]))
            render_citations(msg.get("citations", {}))
        else:
            st.markdown(msg["content"])

# 用户输入
if prompt := st.chat_input("请输入你的问题..."):
    # 显示用户消息
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用后端问答接口
    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/qa/ask",
                    json={
                        "question": prompt,
                        "top_k": 3,
                        "session_id": st.session_state.session_id,
                    },
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data["answer"]
                citations = data.get("citations", {})
            except requests.exceptions.RequestException as e:
                answer = f"请求失败：{e}"
                citations = {}

        st.markdown(highlight_citations(answer))
        render_citations(citations)

    # 保存助手回复
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "citations": citations,
        }
    )


# ---------- 侧边栏：文件管理 ----------
def set_flash(kind: str, message: str) -> None:
    """暂存一条提示，等下一次 rerun 再显示。

    Streamlit 中 st.success/st.error 之后紧跟 st.rerun()，本次运行的输出会被丢弃，
    用户什么都看不到，所以用 session_state 中转一下。
    """
    st.session_state.flash = (kind, message)


with st.sidebar:
    st.header("📁 文档管理")

    flash = st.session_state.get("flash")
    if flash:
        kind, message = flash
        (st.success if kind == "success" else st.error)(message)
        del st.session_state["flash"]

    # --- 上传 ---
    # 用 key 控制 file_uploader，上传成功后换一个 key，把已选文件清空。
    if "uploader_round" not in st.session_state:
        st.session_state.uploader_round = 0
    uploaded = st.file_uploader(
        "上传文档（PDF / Markdown / TXT）",
        type=["pdf", "md", "txt"],
        key=f"uploader_{st.session_state.uploader_round}",
    )
    # 按钮必须始终渲染：若写成 `uploaded is not None and st.button(...)`，
    # Python 的 and 会短路，没选文件时按钮根本不会被渲染，看起来就像"无法上传"。
    confirm_upload = st.button("确认上传", disabled=uploaded is None)

    if confirm_upload and uploaded is not None:
        with st.spinner("上传并入库中..."):
            try:
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                resp = requests.post(
                    f"{BACKEND_URL}/documents/upload",
                    files=files,
                    timeout=600,
                )
                resp.raise_for_status()
                data = resp.json()
                set_flash(
                    "success",
                    f"{data.get('message', '上传成功')}：{data.get('chunks', 0)} 个 chunk",
                )
            except requests.exceptions.RequestException as e:
                set_flash("error", f"上传失败：{e}")
        invalidate_documents_cache()
        st.session_state.uploader_round += 1
        st.rerun()

    # --- 重建索引 ---
    if st.button(
        "🔄 重建索引",
        help="重新扫描 documents 目录并全部入库。Qdrant 数据被清空后可用它恢复。",
    ):
        with st.spinner("正在重新入库..."):
            try:
                resp = requests.post(f"{BACKEND_URL}/documents/reindex", timeout=900)
                resp.raise_for_status()
                data = resp.json()
                set_flash(
                    "success",
                    f"{data['message']}（{data.get('chunks', 0)} 个 chunk）",
                )
            except requests.exceptions.RequestException as e:
                set_flash("error", f"重建索引失败：{e}")
        invalidate_documents_cache()
        st.rerun()

    st.divider()

    # --- 文档列表 ---
    st.subheader("已入库文档")
    try:
        docs = fetch_documents()
    except requests.exceptions.RequestException as e:
        docs = []
        st.error(f"获取列表失败：{e}")

    if not docs:
        st.caption("暂无文档")
    else:
        for doc in docs:
            col1, col2 = st.columns([4, 1])
            with col1:
                # 只显示文件名，隐藏完整路径
                display_name = (
                    doc.get("original_name")
                    or doc["source"].split("/")[-1].split("\\")[-1]
                )
                st.text(f"{display_name} ({doc['chunks']} chunks)")
            with col2:
                if st.button("🗑", key=f"del_{doc['source']}"):
                    try:
                        resp = requests.post(
                            f"{BACKEND_URL}/documents/delete",
                            json={"source": doc["source"]},
                            timeout=10,
                        )
                        resp.raise_for_status()
                        # 和上传一样：先暂存提示，再 rerun，否则 st.success 会被丢弃
                        set_flash("success", f"已删除 {display_name}")
                    except requests.exceptions.RequestException as e:
                        set_flash("error", f"删除失败：{e}")
                    invalidate_documents_cache()
                    st.rerun()
    st.divider()
    st.subheader("💬 当前会话")

    # 手动输入 Session ID
    sid_input = st.text_input(
        "Session ID", value=st.session_state.session_id, key="sid_input"
    )
    if st.button("应用 Session ID"):
        st.session_state.session_id = sid_input
        st.session_state.messages = []  # 切换会话时清空当前显示的聊天
        st.rerun()

    st.caption(f"当前使用：`{st.session_state.session_id}`")

    if st.button("🗑 清空当前会话历史"):
        st.session_state.messages = []
        try:
            requests.post(
                f"{BACKEND_URL}/qa/clear",
                json={"session_id": st.session_state.session_id},
                timeout=10,
            )
        except requests.exceptions.RequestException:
            pass
        st.rerun()
