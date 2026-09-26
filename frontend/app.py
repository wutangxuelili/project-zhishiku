import uuid

import requests
import streamlit as st

# 后端地址（可通过环境变量覆盖）
BACKEND_URL = "http://127.0.0.1:8000"
import re


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
with st.sidebar:
    st.header("📁 文档管理")

    # --- 上传 ---
    uploaded = st.file_uploader(
        "上传文档（PDF / Markdown / TXT）",
        type=["pdf", "md", "txt"],
    )
    if uploaded is not None and st.button("确认上传"):
        with st.spinner("上传并入库中..."):
            try:
                files = {"file": (uploaded.name, uploaded.getvalue(), uploaded.type)}
                resp = requests.post(
                    f"{BACKEND_URL}/documents/upload",
                    files=files,
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                st.success(f"上传成功：{data['chunks']} 个 chunk")
                st.rerun()
            except requests.exceptions.RequestException as e:
                st.error(f"上传失败：{e}")

    st.divider()

    # --- 文档列表 ---
    st.subheader("已入库文档")
    try:
        resp = requests.get(f"{BACKEND_URL}/documents/list", timeout=10)
        resp.raise_for_status()
        docs = resp.json().get("documents", [])
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
                        st.success("已删除")
                        st.rerun()
                    except requests.exceptions.RequestException as e:
                        st.error(f"删除失败：{e}")
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
