# 代码审查自查清单

> **用途**：提交代码前的最后一道防线。清单是流程，不依赖当天的状态——人脑在疲劳时一定会忘。
>
> **怎么用**：
> 1. 先跑自动检查（见下方「自动检查命令」），能自动发现的问题不要靠眼睛
> 2. 再逐条过下面的清单，每条都回到代码里确认，不要凭印象打勾
> 3. 不通过的项，记到「审查发现」里：**位置 + 严重度 + 处理方式**
> 4. 严重度高的必须当轮修掉；否则要么建 issue，要么写进「已知限制」
>
> **勾选状态的含义**：`[x]` = 本次审查确认通过；`[ ]` = 本次审查**未通过**（原因见该项后的说明）。
> 每次审查都重新过一遍，不要沿用上一次的勾。

---

## 自动检查命令

```bash
# 静态检查（能自动发现的问题别靠肉眼）
flake8 --max-line-length=100 --extend-ignore=E203,W503 app frontend tests.py

# 语法编译检查
python -m py_compile app/*.py app/**/*.py frontend/app.py tests.py

# 密钥泄漏扫描
grep -rnE "(api_key|password|secret)\s*=\s*[\"'][^\"']+" --include=*.py .

# 遗留调试语句
grep -rn "print(\|\[DEBUG\]\|TODO\|FIXME" --include=*.py app frontend

# 依赖漏洞（需先安装 pip-audit）
pip-audit -r requirements.txt
```

---

## 一、正确性

- [x] 所有函数都有明确的返回值，且与文档一致 —— 已逐个核对 `utils/` 与 `services/` 全部函数
- [x] 循环边界正确 —— 代码中无手写 `range(n)` 边界逻辑
- [x] 条件判断覆盖所有分支 —— `llm_client.get_llm_client()` 的 provider 分支覆盖 deepseek/qwen
- [x] 异步函数中使用 `await`，没有遗漏 —— 全项目仅 `upload_document` 一个 async 函数，`await file.read()` 正确
- [x] 数据库/向量库操作后，检查是否真的写入成功 —— `upsert(..., wait=True)` / `delete(..., wait=True)` 都等待确认
- [ ] 配置项与实际实现一致 —— `RETRIEVAL_CANDIDATES` / `RERANK_CANDIDATES` 在 `config.py` 和 `.env` 里存在，但**代码从未使用**（见发现 #9）

## 二、边界情况

- [x] 空字符串、空列表、`None` 是否处理 —— `embed_texts([])` 返回 `[]`；`split_segments` 跳过空文本；`ingest_file` 空文档返回 0
- [x] 用户输入为空时是否有合理提示 —— 前端 `st.chat_input` 空值不触发请求
- [x] 文件不存在时是否返回 404 而非 500 —— `/documents/delete` 对不存在的 source 返回 404（已实测）
- [x] Qdrant 集合为空时，检索接口是否返回空列表而非报错 —— `vector_search` 先判断 `collection_exists`
- [x] 分页/scroll 的 `offset` 为 `None` 时是否正确退出循环 —— `list_sources` 里有 `if offset is None: break`
- [x] 上传接口对畸形入参的处理 —— `UploadFile.filename` 类型是 `str | None`，原来直接丢给 `os.path.splitext` 会抛 `TypeError` 变成 500，**本次已修复为 400**（见发现 #1）

## 三、安全

- [x] `.env` 文件在 `.gitignore` 中 —— `.gitignore:4` 已确认（`git check-ignore -v .env` 命中）
- [x] 代码中没有硬编码的 API Key、密码 —— 全仓库 grep 无命中，密钥只从环境变量读取
- [ ] 文件上传接口校验了扩展名和 **MIME 类型** —— 只校验了扩展名（见发现 #10）
- [x] 文件路径拼接没有 `../../` 风险 —— 落盘文件名由服务端用内容哈希生成，**不采用用户传入的文件名**，天然免疫
- [x] 删除文件前检查路径是否在 `UPLOAD_DIR` 内 —— `documents.py` 有 `upload_dir in source_path.parents` 判断
- [x] CORS 配置没有 `allow_origins=["*"]` + `allow_credentials=True` —— 项目未启用 CORS 中间件（前端是服务端调用，不需要）
- [ ] 接口有鉴权 —— 无任何鉴权，拿到 8000 端口就能上传/删除（见发现 #11）

## 四、健壮性

- [x] LLM 调用有超时设置 —— `OpenAI(..., timeout=60.0)`
- [ ] LLM 调用失败时有 fallback 或错误提示 —— 无重试、无降级，异常直接冒泡成 500（见发现 #12）
- [x] 外部依赖连接失败时不会让整个应用卡死 —— 模型加载原来每次都会联网检查更新，Hub 不通时卡在 5 次重试上（实测 `/health` 超过 5 分钟不返回），**本次已修复为缓存优先离线加载**（见发现 #2）
- [ ] 上传大文件时不会一次性读入内存 —— `content = await file.read()` 全量读入，且无大小限制（见发现 #14）
- [x] 后台任务（如入库）的异常被捕获并记录日志 —— `upload_document` / `reindex_documents` 都有 try/except 并返回带原因的 500

## 五、性能

- [x] 模型（BGE）只加载一次（单例） —— `embedder.get_embedding_model()` 进程内单例 + 懒加载
- [x] 批量向量化用 `embed_texts`，不循环调用 `embed_query` —— `ingest_service.ingest_file` 用 `embed_texts([...])`
- [x] Redis 会话设置了过期时间 —— `append_message` 每次写入都 `expire`
- [x] Qdrant 查询没有拉取不必要的字段 —— `list_sources` 的 scroll 传了 `with_vectors=False`
- [x] 前端请求没有重复调用同一个接口 —— 原来每次 rerun（含每问一句）都会打一次 `/documents/list`，**本次已加 5 秒缓存 + 变更后主动清缓存**（见发现 #8）

## 六、可读性

- [x] 变量名能表达含义 —— 无 `x` / `data` 之类的模糊命名
- [x] 函数职责单一 —— services 负责编排、utils 只封装单一外部依赖
- [x] 关键逻辑有注释说明"为什么"而非"做什么" —— 如幂等入库、`HF_ENDPOINT` 的设置时机、`and` 短路陷阱
- [x] 复杂函数有 docstring —— 全项目函数均有
- [x] 没有遗留的 `print` 调试语句 —— 原有 14 处 `print`（含 5 处 `[DEBUG]`），**本次已全部改为 `logging`**（见发现 #3）
- [x] 模块级 import 都在文件顶部 —— 原有 2 处 E402，**本次已修复**（见发现 #4）

## 七、一致性

- [x] 所有路由都用 `APIRouter`，没有混用 `@app.get` —— `qa.py` / `documents.py` 均用 `APIRouter`（`/health` 是应用级端点，用 `@app.get` 合理）
- [ ] 所有 Pydantic 模型放在 `schemas/` 目录 —— 请求模型就近定义在各自 router 里，没有 `schemas/` 目录（见发现 #16）
- [x] 所有工具函数放在 `utils/` 目录
- [x] 命名风格统一（Python 用 `snake_case`）
- [x] 返回格式统一 —— 问答返回 `{answer, citations}`，文档操作返回 `{message, ...}`
- [x] 配置集中管理 —— `HF_ENDPOINT` 原来只散落在 `os.environ` 里，**本次已收进 `Settings`**（见发现 #7）

## 八、可测试性

- [ ] 核心函数不依赖全局状态（或通过参数传入） —— `utils/` 里有模块级单例（`_model` / `_client`），不利于单测（见发现 #17）
- [ ] 有单元测试覆盖关键路径（pytest） —— 无。仓库里的 `tests.py` 名字有误导性，它是批量入库脚本，不是测试用例（见发现 #13）
- [ ] 测试用 mock 替代真实 LLM 调用 —— 无测试
- [ ] 测试数据不依赖本地文件（用临时目录） —— 无测试

## 九、依赖管理

- [x] `requirements.txt` 已锁版本 —— 119 项全部用 `==`
- [x] 没有 Windows 专有包在 Linux 镜像里 —— `pywin32` 已加 `sys_platform == "win32"` 环境标记
- [x] 前后端依赖分离 —— 已拆出独立的 `frontend/requirements.txt`（前端不装 torch，省下约 5 GB）
- [ ] 定期跑 `pip-audit` 检查已知漏洞 —— 当前环境未安装 `pip-audit`，本轮未执行（见发现 #15）

## 十、文档

- [x] README 有项目简介、架构图、快速开始 —— 见 `README.md`
- [x] 所有 API 在 `/docs` 中有描述 —— FastAPI 自动生成，router 有 tags，函数有 docstring
- [x] `.env.example` 列出了所有必需的环境变量（不含真实值） —— 见 `.env.example`
- [x] 有 `docs/` 目录存放详细文档 —— `ARCHITECTURE.md` / `DEMO.md` / 本文件

## 十一、Docker/部署

- [x] `.dockerignore` 排除了 `.venv/`、`.git/`、`qdrant_storage/`
- [x] Dockerfile 使用 `--no-cache-dir` 减小镜像
- [x] `docker-compose.yml` 中数据卷正确挂载 —— `qdrant_data` / `redis_data` / `hf_cache` / `./documents`
- [x] 环境变量通过 `env_file` 注入，不硬编码
- [x] 容器内服务名用于内部通信 —— `QDRANT_HOST=qdrant`、`REDIS_HOST=redis`、`BACKEND_URL=http://backend:8000`
- [ ] `depends_on` 配了健康检查条件 —— 只写了服务名，没有 `condition: service_healthy`，存在启动竞态（见发现 #18）
- [ ] 构建产物完整 —— `.dockerignore` 里的 `*.md` 会把 Markdown 排除出构建上下文；目前靠 bind mount 兜住，去掉挂载就会缺文件（见发现 #19）

## 十二、提交前

- [x] `git status` 确认没有意外文件被追踪 —— 已核对
- [x] `git diff` 检查每一处改动 —— 已逐文件核对
- [x] 提交信息清晰（`feat:` / `fix:` / `docs:` 前缀）
- [x] 没有 `TODO` / `FIXME` 遗留
- [x] 跑一遍端到端测试（上传 → 提问 → 引用 → 多轮对话 → 删除）—— **15/15 通过**，见下方记录

---

## 本次审查记录

**审查范围**：`app/`、`frontend/`、`tests.py`、Dockerfile、`docker-compose.yml`
**自动检查结果**：`flake8` 0 问题 · `py_compile` 通过 · 无硬编码密钥 · 无 `print`/`TODO` 遗留

### 端到端验证（真实调用，非 mock）

```
== 1. 健康检查 ==        PASS  GET /health 200 · embedding.dim == 512
== 2. 上传 ==            PASS  200 · chunks > 0
== 3. 列表 ==            PASS  列表包含刚上传的文件
== 4. 提问（首次）==      PASS  200 · 回答非空 · 带回引用 · 答案含预期标记
== 5. 多轮追问 ==        PASS  追问有回答
== 6. 边界：文件名为空 == PASS  返回 400（修复前是 500）
== 7. 边界：删除不存在 == PASS  返回 404
== 8. 删除 ==            PASS  200 · 删除后列表不含该文件

结果：PASS=15 FAIL=0
```

### 审查发现

| # | 维度 | 问题 | 位置 | 严重度 | 处理 |
|---|---|---|---|---|---|
| 1 | 边界 | `UploadFile.filename` 为 `None` 时 `os.path.splitext` 抛 `TypeError` → 500 | `app/routers/documents.py` | 中 | ✅ 已修（改 400） |
| 2 | 健壮性 | 模型已缓存仍每次联网检查更新，Hub 不通时卡死数分钟 | `app/utils/embedder.py` | **高** | ✅ 已修（缓存优先离线加载） |
| 3 | 可读性 | 14 处 `print` 调试语句（含 5 处 `[DEBUG]`） | 6 个文件 | 低 | ✅ 已修（改 logging） |
| 4 | 可读性 | E402 模块级 import 不在文件顶部 ×2 | `documents.py`、`frontend/app.py` | 低 | ✅ 已修 |
| 5 | 一致性 | E302 函数前缺空行 | `frontend/app.py` | 低 | ✅ 已修 |
| 6 | 可读性 | 未使用的 import：`shutil`、`settings` | `documents.py`、`qa_service.py` | 低 | ✅ 已修 |
| 7 | 一致性 | `HF_ENDPOINT` 未纳入 `Settings`，只散落在 `os.environ` | `app/config.py` | 低 | ✅ 已修 |
| 8 | 性能 | 前端每次 rerun 都请求 `/documents/list` | `frontend/app.py` | 中 | ✅ 已修（5s 缓存 + 主动失效） |
| 9 | 正确性 | `RETRIEVAL_CANDIDATES` / `RERANK_CANDIDATES` 配置项从未被使用 | `app/config.py` | 低 | ⚠️ 遗留（属未实现功能，见后续计划） |
| 10 | 安全 | 上传只校验扩展名，未校验 MIME | `app/routers/documents.py` | 低 | ⚠️ 遗留 |
| 11 | 安全 | 接口无鉴权，可任意上传/删除 | 全局 | **高** | ⚠️ 遗留（已列入已知限制） |
| 12 | 健壮性 | LLM 调用无重试/降级，失败即 500 | `app/services/qa_service.py` | 中 | ⚠️ 遗留 |
| 13 | 可测试性 | 无单元测试；`tests.py` 命名误导 | 全局 | 中 | ⚠️ 遗留 |
| 14 | 健壮性 | 上传无大小限制且全量读入内存 | `app/routers/documents.py` | **高** | ⚠️ 遗留 |
| 15 | 依赖 | 未执行 `pip-audit` | — | 中 | ⚠️ 遗留（环境无此工具） |
| 16 | 一致性 | Pydantic 模型散落在 router，未集中到 `schemas/` | `routers/*.py` | 低 | ⚠️ 遗留（当前规模可接受） |
| 17 | 可测试性 | `utils/` 依赖模块级单例，不易单测 | `app/utils/*.py` | 低 | ⚠️ 遗留 |
| 18 | 部署 | `depends_on` 无 healthcheck 条件，存在启动竞态 | `docker-compose.yml` | 中 | ⚠️ 遗留 |
| 19 | 部署 | `.dockerignore` 的 `*.md` 会排除 Markdown | `.dockerignore` | 低 | ⚠️ 遗留 |

### 环境层发现（不属于代码，但会阻塞开发）

| 问题 | 现象 | 处理 |
|---|---|---|
| `docker compose` 子命令不存在 | `docker: unknown command: docker compose` | 用户级 `~/.docker/cli-plugins` 被 Docker Desktop 清空。**往该目录复制 `.exe` 会被 Docker Desktop 在下次启动时删掉**，持久做法是在 `~/.docker/config.json` 加 `cliPluginsExtraDirs` 指向 Docker Desktop 的 `resources\cli-plugins` |
| HuggingFace 镜像跳转行为不稳定 | 同一镜像站点，`307` + 同站相对跳转可用，`308` + 跨站绝对跳转会让 `huggingface_hub` 报 `Distant resource does not seem to be on huggingface.co` | 端点写进 `.env` 便于切换；有本地缓存时不再走网络（发现 #2） |

### 遗留问题的建议优先级

1. **P0**：上传大小限制（发现 #14）—— 当前可以被一个超大文件打满内存
2. **P0**：鉴权（发现 #11）—— 生产部署前必须补
3. **P1**：LLM 超时重试 + 降级（发现 #12）、`depends_on` healthcheck（发现 #18）
4. **P1**：单元测试与 CI（发现 #13）
5. **P2**：MIME 校验、`schemas/` 目录、`pip-audit` 纳入 CI、`.dockerignore` 收紧
