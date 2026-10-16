# 知识库问答系统（RAG Knowledge Base QA）

基于 RAG（检索增强生成）的中文知识库问答系统。上传 PDF / Markdown / TXT 文档，用自然语言提问，
系统会检索相关内容并**给出带引用来源的回答**，支持多轮对话。

> 一句话理解：文档 → 切分 → 向量化 → 存进 Qdrant；提问 → 向量检索 → 把命中的片段喂给大模型 → 带引用作答。

---

## 功能列表

| 功能 | 说明 |
|---|---|
| 📄 文档上传 | 支持 PDF / Markdown / TXT，按内容哈希去重命名，自动解析与入库 |
| 🔍 向量检索 | BGE 中文向量模型 + Qdrant 余弦相似度检索 Top-K 片段 |
| 📖 引用来源 | 回答中的 `[1]` `[2]` 可展开为原文片段，附文件名、页码、相似度分数 |
| 💬 多轮对话 | 会话历史存 Redis，追问会自动改写成独立问题后再检索 |
| 🗂️ 文档管理 | 列出已入库文档及 chunk 数，支持按来源删除（向量 + 本地文件一起删） |
| ♻️ 版本替换 | 同一个文件名的文档改版重传时，旧版本的向量与本地文件会被自动清理，不会新旧混检 |
| 🔄 重建索引 | 一键把 `documents/` 目录下的全部文档重新入库，用于向量库被清空后恢复 |
| 🩺 健康检查 | `/health` 返回 Qdrant 连接状态与向量维度，便于排障 |
| ✅ 离线自检 | `python scripts/verify_fixes.py` —— 43 项断言，不依赖 Docker/Qdrant/大模型，可直接进 CI |

支持 PDF / MD / TXT 三种格式；扫描件（图片型 PDF）无法提取文本。

---

## 系统架构

```
      浏览器
        │
        ├─► Streamlit :8501 ─► FastAPI :8000
        │                          ├─► Qdrant :6333   向量库 kb_qa（仅绑本机 127.0.0.1）
        └──────────────────────────┴─► Redis  :6379   会话历史（仅绑本机 + 密码认证）
```

FastAPI 还会出网访问 **DeepSeek / 通义千问 API**（生成回答）和 **HuggingFace**（首次下载向量模型）。

**两条核心链路：**

- **入库**：上传 → 按扩展名解析（PDF 逐页 / MD 按标题）→ 切分成 400 字左右的 chunk → BGE 转向量 → 写入 Qdrant
- **问答**：提问 → 读 Redis 历史 → （有历史时）LLM 改写追问 → 向量检索 Top-K → 拼成 `<资料 id="N">` 资料块（正文里的同形标记先消毒）→ LLM 作答 → 回写历史

> 组件职责、时序图、数据模型与关键设计取舍见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 技术栈

| 层次 | 选型 |
|---|---|
| 后端框架 | FastAPI 0.141（自带 OpenAPI / Swagger UI，Pydantic 校验） |
| 前端 | Streamlit 1.64（纯 Python 写聊天式 UI） |
| 向量数据库 | Qdrant 1.19（存 chunk 向量 + payload，COSINE 距离）——镜像 tag 在 `docker-compose.yml` 里**钉死**为 `v1.19.1`，不用 `latest` |
| 向量模型 | BAAI/bge-small-zh-v1.5（中文小模型，512 维，CPU 可跑） |
| 推理框架 | sentence-transformers 3.2 + PyTorch 2.14（**CPU 版**） |
| 大模型 | DeepSeek / 通义千问（走 `openai` SDK 的 OpenAI 兼容协议，换模型只改 `.env`） |
| 会话存储 | Redis 7（List 结构存多轮历史，带 TTL 自动过期） |
| 文档解析 | pdfplumber / pdfminer.six（PDF 按页提取文本，保留页码） |
| 文本切分 | langchain-text-splitters（Markdown 标题切分 + 递归字符切分） |
| 部署 | Docker Compose（四个服务一条命令拉起） |

---

## 目录结构

```
project-zhishiku/
├── app/                    # 后端（FastAPI），分层见下方说明
├── frontend/app.py         # Streamlit 界面：聊天区 + 侧边栏文档管理
├── documents/              # 文档存储目录（哈希命名），由 compose 挂载进容器
│                           # 仓库里只保留 .gitkeep，上传内容不进 Git
├── test_docs/              # 示例文档（sample.md / ceshiwendang.pdf）
├── scripts/verify_fixes.py # 离线自检：版本替换 / 陈旧文件自愈 / 路径校验 / 参数约束（不需要 Docker）
├── tests.py                # ⚠️ 不是单元测试，是批量入库脚本
├── docs/                   # ARCHITECTURE.md（架构与取舍）、code_review_checklist.md（审查清单与修复记录）
├── docker-compose.yml      # 四服务编排：qdrant / redis / backend / frontend
├── backend.Dockerfile      # 后端镜像（CPU 版 torch 多阶段构建）；另有 frontend.Dockerfile
├── requirements.txt        # 后端依赖（pip freeze 锁定版本）
├── LICENSE                 # MIT
└── .env.example            # 配置模板；不建 .env 也能一键启动，只是不能提问
```

`app/` 内部按职责分层：`main.py`（入口 / `/health`）、`config.py`（集中读 `.env`）、
`routers/`（`qa.py` 问答、`documents.py` 上传/重建/列表/删除）、
`services/`（`qa_service.py` 问答编排、`ingest_service.py` 入库编排）、
`utils/`（`loader` / `splitter` / `embedder` / `qdrant_client` / `redis_client` / `llm_client`）。

---

## 快速开始

> 下面是压缩版。**首次部署请直接看 [`DEPLOY.md`](DEPLOY.md)** —— 那里有逐个变量的说明、
> 每步的预期输出、验证清单和 10 个常见问题的排查步骤。

**前置要求**（完整清单见 [`DEPLOY.md`](DEPLOY.md#前置要求)）：

- Docker Desktop（含 Compose v2，命令是 `docker compose`）
- 磁盘空间 ≥ 10 GB（后端镜像 2.67 GB + 前端 801 MB + 数据卷）
- 端口 8000 / 8501 / 6333 / 6379 未被占用（被占用时见 [DEPLOY.md 的 Q1](DEPLOY.md#q1启动时报端口被占用port-is-already-allocated--bind-address-already-in-use)）
- **想让问答能用**，还需要一个 LLM API Key：[DeepSeek](https://platform.deepseek.com) 或[通义千问](https://bailian.console.aliyun.com)

**一键启动**（首次构建约 3~10 分钟）：

```bash
git clone https://github.com/wutangxuelili/project-zhishiku.git
cd project-zhishiku
docker compose up -d --build
```

**不需要先准备 `.env`**：四个容器会直接起来，上传文档、文档管理、向量检索都能用。
只有"生成回答"需要 Key —— 想提问时再补上，然后重启后端即可：

```bash
cp .env.example .env                                  # 编辑 .env，填 LLM_API_KEY
docker compose up -d --force-recreate backend
```

> 没配 Key 时提问不会报 500，界面会直接提示你该怎么填；`GET /health` 里的
> `llm.api_key_configured` 也能一眼看出配没配。

**启动后访问**：

| 地址 | 说明 |
|---|---|
| http://localhost:8501 | 前端界面（从这里开始用） |
| http://localhost:8000/docs | 后端 Swagger API 文档 |
| http://localhost:8000/health | 健康检查，返回 `{"status":"ok",...}` |
| http://localhost:6333/dashboard | Qdrant 控制台 |

**第一次使用**：

1. 打开 http://localhost:8501，左侧「📁 文档管理」上传一个 PDF / MD / TXT，点「确认上传」
2. 上传成功后「已入库文档」会列出该文档及 chunk 数
3. 在底部输入框提问，回答带 `[1]` `[2]` 引用标记，可展开看原文片段与相似度

> ⏱️ **首次提问会慢一会儿**：后端要下载 BGE 向量模型（约 95 MB）并加载进内存。
> 之后模型缓存在 `hf_cache` 卷里，重启不重复下载。

**常用命令**：

```bash
docker compose ps               # 看四个容器状态
docker compose logs -f backend  # 跟随后端日志
docker compose stop             # 停止（保留数据）
docker compose down -v          # 停止并清空数据卷（不可恢复）
```

> 重启电脑后容器不会自动拉起（优雅停止被视为「手动停止」，`restart: unless-stopped` 不再生效），
> 重新执行一次 `docker compose up -d` 即可，数据都还在卷里。

---

## API 文档

Base URL：`http://localhost:8000`　交互式文档：`/docs`（Swagger）/ `/redoc` / `/openapi.json`

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查：Qdrant 状态、集合信息、向量维度 |
| `POST` | `/qa/ask` | 提问，返回回答与引用 |
| `POST` | `/qa/clear` | 清空指定会话的历史 |
| `POST` | `/documents/upload` | 上传文档并入库（multipart） |
| `POST` | `/documents/reindex` | 把 `documents/` 目录下所有文档重新入库 |
| `GET` | `/documents/list` | 列出已入库文档及 chunk 数 |
| `POST` | `/documents/delete` | 按来源删除文档（向量 + 本地文件） |

### `GET /health`

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "qdrant": { "exists": true, "points_count": 15, "status": "green" },
  "embedding": { "model": "BAAI/bge-small-zh-v1.5", "dim": 512 },
  "llm": { "provider": "deepseek", "model": "deepseek-chat", "api_key_configured": true }
}
```

> `llm.api_key_configured` 为 `false` 说明还没填 Key，这时上传/检索正常、**提问会被拒并给出填写指引**。

### `POST /qa/ask`

`session_id` 为空则本次不读写历史（单轮模式）。回答里的 `[1]` 与 `citations` 的键一一对应。
没配置 LLM Key 时，`answer` 会直接返回一段"该去哪里填 Key"的提示（不是 500）。

`top_k` 不传时取 `.env` 里的 `TOP_K`（默认 3），**上限 20** —— 防止客户端要一个极大的值把
上下文和大模型费用一起放大。前端已不再传 `top_k`，改条数只需改 `.env` 并重启后端。

```bash
curl -X POST http://localhost:8000/qa/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "这篇文档讲了什么？", "top_k": 3, "session_id": "demo-001"}'
```

```json
{
  "answer": "文档主要介绍了…… [1]",
  "citations": {
    "1": { "text": "命中的原文片段……", "source": "documents/f0ed6380caff6f7d.md",
           "original_name": "sample.md", "page": null, "score": 0.7351 }
  }
}
```

### `POST /qa/clear`

```bash
curl -X POST http://localhost:8000/qa/clear \
  -H "Content-Type: application/json" -d '{"session_id": "demo-001"}'
```

### `POST /documents/upload`

```bash
curl -X POST http://localhost:8000/documents/upload -F "file=@./你的文档.pdf"
```

```json
{ "message": "上传并入库成功", "filename": "9b3a816e795037b1.pdf", "original_name": "你的文档.pdf",
  "chunks": 6, "replaced_chunks": 0, "removed_old_files": 0 }
```

> 重复上传同一份文件不会产生重复数据，返回 `文件已存在，已重新入库`。
> 落盘文件按 `sha256(内容)[:16] + 扩展名` 命名，因此内容相同即同一个文件。
>
> **文档改版时会自动替换旧版本**：内容变了 → 落盘名变了 → 旧版本的向量不会自己失效，
> 所以上传成功后后端会按 `original_name` 把同名的旧版本清掉，`replaced_chunks` 就是清掉的
> 旧 chunk 数，`removed_old_files` 是顺手删掉的旧本地文件数。**同一个文件名视为同一份文档**，
> 想同时保留两版就把文件名改掉。

### `POST /documents/reindex`

```bash
curl -X POST http://localhost:8000/documents/reindex
```

```json
{ "message": "已重新入库 3 个文件", "files": 3, "chunks": 15, "purged_points": 0 }
```

> `purged_points`：如果 `documents/` 里有"文件名是内容哈希、内容却被手动改过"的文件，
> 重建索引会把它改名成正确的哈希名，并清理旧名字下的向量（清理数量就是它）。正常情况下是 0。

### `GET /documents/list`

```bash
curl http://localhost:8000/documents/list
```

```json
{ "documents": [ { "source": "documents/f0ed6380caff6f7d.md", "chunks": 8, "original_name": "sample.md" } ] }
```

### `POST /documents/delete`

删除 Qdrant 中该来源的全部向量，并删除位于上传目录内的本地文件。

```bash
curl -X POST http://localhost:8000/documents/delete \
  -H "Content-Type: application/json" -d '{"source": "documents/f0ed6380caff6f7d.md"}'
```

```json
{ "message": "删除成功", "source": "documents/f0ed6380caff6f7d.md", "deleted_chunks": 8 }
```

---

## 已知限制

诚实地记录当前没做好的地方：

1. **配置项与实现不符**：`RETRIEVAL_CANDIDATES`、`RERANK_CANDIDATES` 在 `config.py` / `.env` 里存在，但代码从未使用。
   实际情况是**单路向量检索直接取 Top-K**，没有「召回 + 重排」两阶段，也没有 CrossEncoder 重排模型。
2. **检索没有过滤和阈值**：不能限定「只在某个文档里提问」，也没有相似度阈值，
   即使命中的片段完全不相关，也照样塞进上下文（只能靠提示词让模型回答「无法回答」）。
3. **`original_name` 会丢，版本替换只在"上传路径"生效**：原始文件名只在上传时记录。
   通过「重建索引」或 `tests.py` 入库的文档没有这个名字，前端会退化成显示哈希文件名，
   而且**凭文件名判断"这是同一份文档的新版本"也就不成立了** —— 换名字后再重建索引，旧向量会留着，
   需要手动删除。根治办法是把文档身份从"文件名"升级为独立的 `doc_id`（见后续计划）。
4. **切分策略较粗**：固定 400 字 / 50 字重叠。PDF 按页切分，跨页的表格和段落会被切断；
   扫描件（图片型 PDF）无法提取文本。
5. **上传是同步阻塞的，且没有大小限制**：解析 + 向量化 + 写库全在一个 HTTP 请求里完成，
   而且 `await file.read()` 会把整个文件读进内存 —— 一个大文件就能打满后端内存。
   没有任务队列、没有进度反馈，前端的上传超时设成了 600 秒来兜底（**提问的超时是 60 秒**）。
6. **无鉴权、无多租户**：任何能访问 8000 端口的人都能上传和删除文档；所有用户共享同一个知识库。
   （中间件这一层已经收紧：Qdrant 6333 与 Redis 6379 都只绑 `127.0.0.1`，Redis 另有密码认证；
   但 8000 / 8501 仍发布在 `0.0.0.0`，需要跨设备访问才有这个必要，不需要就改成只绑本机。）
7. **单进程串行推理**：uvicorn 单 worker，BGE 模型常驻内存；向量化在 FastAPI 的线程池里执行，并发高时会排队。
8. **没有单元测试**：仓库里的 `tests.py` 名字有误导性，它其实是批量入库脚本，不是测试用例。
9. **会话上下文会截断**：只取最近 6 轮历史，没有摘要压缩，长对话早期信息会丢失。
10. **提示词注入只能缓解、不能消灭**：资料已明确标注为"数据不是指令"，正文里冒充分隔标记的片段会被消毒，
    命中的注入话术会打日志告警；但**只要"不可信的文档"和"能下指令的模型"共处一个上下文，注入就有成功空间**。
    真正的根治得靠信任边界（谁能上传）与最小权限，见「数据与合规」一节（见 P1-5）。

---

## 数据与合规

这类系统最容易出事的地方不是代码，而是"数据流到哪儿去了"。这里把话说明白。

### 出网清单（只有这些会离开你的机器）

| 数据 | 去哪 | 什么时候 |
|---|---|---|
| 文档正文（切分后的 chunk） | DeepSeek / 阿里云 DashScope 的 API | 每次提问命中该 chunk 时 |
| 用户提问（含多轮改写后的问题） | 同上 | 每次提问 |
| 最近 6 轮对话历史 | 同上 | 请求里带了 `session_id` 时 |
| 向量模型下载请求 | HuggingFace / hf-mirror | **仅首次部署**（之后走本地缓存，不再发网络请求） |

**不出网**：向量本身、Qdrant 里的 payload、会话历史、上传的原始文件（都留在本机）。

### 现在**没有**做的（内部资料场景下这些就是红线）

1. **没有脱敏**：不识别身份证号、手机号、客户名单，原文直接进提示词。
2. **没有留存与删除策略**：第三方 API 侧是否留存、留多久，由对方条款决定，本项目不做约束，也没有"用完即删"的开关。
3. **没有分级**：机密/内部/公开的资料一视同仁地入库、一视同仁地发出去。
4. **没有审计日志**：谁在什么时候上传了什么、问了什么，只有 Redis 里 1 小时就过期的会话历史，事后不可追溯。
5. **没有租户隔离**：所有人共享同一个知识库与全部文档（见「已知限制」第 6 条）。
6. **没有告知同意流程**：界面上有一条常驻提示（前端侧边栏），但没有"确认我已了解"的交互，也没有使用条款。

### 要用在真实资料上，至少先做这些

- **上传前确认资料级别**；涉密资料改用本地部署的模型 —— 只需把 `.env` 的 `LLM_BASE_URL` 指向自建服务，代码不用改。
- **先脱敏再入库**，或只入库脱敏后的副本。
- **明确告知使用者**数据流向（前端已加常驻提示），必要时补一份使用条款。
- **与模型供应商确认数据处理条款**：是否用于训练、留存多久、能否关闭。
- 需要多部门复用时，先在 Qdrant payload 上加 `tenant`/`owner` 字段并给检索加过滤（当前没有任何过滤）。

---

## 常见问题

只列与代码/设计直接相关的；**部署、端口、镜像、网络相关的问题见 [`DEPLOY.md`](DEPLOY.md#常见问题)**。

**Q：构建时报 `Could not find a version that satisfies the requirement pywin32==312`**

`requirements.txt` 是从 Windows 环境 `pip freeze` 出来的，`pywin32` 没有 Linux 版本。
本仓库已用环境标记处理（`pywin32==312; sys_platform == "win32"`），Linux 下会自动跳过。
如果你重新 freeze 过依赖，注意保留这个标记。

**Q：上传同一个文件提示「文件已存在，已重新入库」，是出问题了吗？**

不是。入库是幂等的：point id 由 `(source, 内容)` 的稳定哈希生成，重复入库只会覆盖同样的向量，
不会产生重复数据。这个分支还有一个用处 —— 向量库被清空后，重新上传就能恢复索引。

**Q：我把同一份文档改了内容再上传，会同时留下两版吗？**

不会（同一文件名）。落盘名是内容哈希，改内容就等于换了个 source，旧向量本来不会失效；
所以上传成功后后端会按 `original_name` 把同名的旧版本一并清掉（向量 + 旧的本地文件），
前端会提示「已替换旧版本（清理 N 个旧 chunk）」。日志里也能看到
`同名替换：original_name=xxx 清理 N 个旧 chunk`。

两个例外要说清楚：

- **同名不同文件**：文件名相同就被视为同一份文档的新版本，旧的那份会被替换。想同时保留，请改文件名。
- **重建索引进来的文档没有 `original_name`**（只有上传路径才知道原始文件名），
  所以**「改文件名后再重建索引」不会触发替换**，旧向量会留着 —— 请用界面的 🗑 删除旧文档。
  另外，如果你手动改的是 `documents/` 里那个哈希名文件的内容，重建索引会自动改名并清理旧向量
  （见 `/documents/reindex` 的 `purged_points`）。

**Q：「已入库文档」是空的，但 `documents/` 目录里明明有文件**

`documents/` 只是文件存储，真正的索引在 Qdrant。如果 Qdrant 数据卷被重建（换机器、`docker compose down -v`），
文档就不会出现在列表里。点侧边栏的「🔄 重建索引」即可把目录里的文档全部重新入库。

**Q：服务起来后第一次提问卡好几分钟，像卡死了**

**已有缓存时不会了。** `app/utils/embedder.py` 用的是**缓存优先**加载：先以
`local_files_only=True` 纯本地加载，只有本地确实没有权重时才走联网分支。
默认的 `local_files_only=False` 会先向 HuggingFace 发请求检查更新，网络不通时卡在重试上——
这正是以前"卡死"的原因，已经改掉。

会慢的只剩两种情况：

- **首次部署、本地还没有缓存**：要下载约 95 MB 权重，属正常，等它下完即可；
- **网络不通且本地无缓存**：会走联网分支并重试，此时看起来就是卡住。想彻底禁网就把 `.env` 里的
  `HF_HUB_OFFLINE=1`（本地有缓存时直接离线加载；**本地没缓存时开它会立刻报错**，错误信息里写了怎么办）。

另外 `HF_ENDPOINT` 默认指向 `hf-mirror.com`，若报
`Distant resource does not seem to be on huggingface.co`，说明该镜像做了跨站跳转，换回官方端点即可。

---

## 后续计划

- [ ] **两阶段检索**：向量召回 Top-N → CrossEncoder 重排 → Top-K（把现有那两个配置项真正用起来）
- [ ] **检索质量**：加相似度阈值、元数据过滤（按文档/时间范围提问）、「无相关内容」短路
- [ ] **异步入库 + 流式输出**：任务队列 + 进度推送；回答改 SSE 边生成边显示，并支持会话摘要压缩
- [ ] **格式扩展**：DOCX / HTML，以及扫描件 OCR
- [ ] **工程质量**：pytest 单元测试 + GitHub Actions CI，把 `tests.py` 改名为 `batch_ingest.py`
- [ ] **安全**：API Key 鉴权、上传大小限制、多租户隔离

---

## 相关文档

- [`DEPLOY.md`](DEPLOY.md) — 部署指南：前置要求、一键启动、验证清单、常见问题排查
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 组件职责、数据流时序图、数据模型、设计取舍
- [`docs/code_review_checklist.md`](docs/code_review_checklist.md) — 提交前的代码审查自查清单与修复记录
- [`scripts/verify_fixes.py`](scripts/verify_fixes.py) — 离线自检脚本（43 项断言，不需要 Docker）

---

## 许可证

[MIT](LICENSE) © 2026 wutangxuelili

> 这个 LICENSE 是后补的：公开仓库没有许可证文件时默认是"保留所有权利"，
> 别人**法律上不能**使用、修改或分发你的代码 —— 这跟"公开出来给人看"是矛盾的。
> 如果想换成更宽松/更严格的许可（Apache-2.0、AGPL-3.0 等），直接替换 `LICENSE` 文件即可。
