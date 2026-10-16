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
# 离线自检（不需要 Qdrant / Redis / Docker / 大模型）：文档版本替换、陈旧文件自愈、
# 删除路径校验、接口参数约束。全通过时退出码 0，可直接接进 CI
python scripts/verify_fixes.py

# 静态检查（能自动发现的问题别靠肉眼）
# ⚠️ flake8 没有写进任何依赖文件，得先 `pip install flake8`，否则这条根本跑不起来
flake8 --max-line-length=100 --extend-ignore=E203,W503 app frontend tests.py scripts

# 语法编译检查
python -m py_compile app/*.py app/**/*.py frontend/app.py tests.py scripts/verify_fixes.py

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
- [ ] 配置项与实际实现一致 —— `RETRIEVAL_CANDIDATES` / `RERANK_CANDIDATES` 在 `config.py` 和 `.env` 里存在，但**代码从未使用**（见发现 #9）；`TOP_K` 已在本轮接入（`routers/qa.py` / `services/qa_service.py` / `utils/qdrant_client.py`），不再是死配置

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
- [x] 中间件端口不对外暴露、Redis 有密码 —— 6333/6379 均绑 `127.0.0.1`，redis 用 `--requirepass`（**本轮之前两项都不满足**：
  只写 `"6333:6333"` 等于绑 `0.0.0.0`，Redis 也没有密码，等于把全部文档原文和会话历史摆给同网段所有人）

## 四、健壮性

- [x] LLM 调用有超时设置 —— `OpenAI(..., timeout=60.0)`
- [ ] LLM 调用失败时有 fallback 或错误提示 —— 无重试、无降级，异常直接冒泡成 500（见发现 #12）
- [x] 外部依赖连接失败时不会让整个应用卡死 —— `utils/embedder.py` 的 `_load_model()` **先 `local_files_only=True` 纯本地加载，失败才联网**，已有缓存时不发任何网络请求；实测 `HF_HUB_OFFLINE=1`（完全禁网）下可用本地缓存正常加载（dim=512）。本地无缓存且禁网时抛 `RuntimeError` 并给出处理办法，不再卡在重试上（见发现 #2）。**注意：本条上一轮曾被标为"已修复"但代码里并没有实现，本轮才是真的落地**
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
- [ ] 有单元测试覆盖关键路径（pytest） —— 仍无 pytest 用例：仓库里的 `tests.py` 是批量入库脚本，
  不是测试。**部分兑现**：第二轮加了 `scripts/verify_fixes.py`（43 项断言，桩对象 + 临时目录，
  不依赖 Docker/Qdrant/大模型），把版本替换、陈旧文件自愈、删除路径校验、参数约束钉住了；
  但它是一次性脚本、不是能增量成长的测试套件（见发现 #13）
- [ ] 测试用 mock 替代真实 LLM 调用 —— `scripts/verify_fixes.py` 用桩对象替代了 Qdrant 与向量化，
  但 LLM 调用路径（`qa_service.rewrite_query` / `chat`）仍无覆盖
- [ ] 测试数据不依赖本地文件（用临时目录） —— 无测试

## 九、依赖管理

- [x] `requirements.txt` 已锁版本 —— 119 项全部用 `==`
- [x] 没有 Windows 专有包在 Linux 镜像里 —— `pywin32` 已加 `sys_platform == "win32"` 环境标记
- [x] 前后端依赖分离 —— 已拆出独立的 `frontend/requirements.txt`（前端镜像内仅 40 个包 / 440 MB；若统一则在 2.67 GB 的后端依赖之上再叠加，省下约 1.87 GB）
- [ ] 定期跑 `pip-audit` 检查已知漏洞 —— 当前环境未安装 `pip-audit`，本轮未执行（见发现 #15）

## 十、文档

- [x] README 有项目简介、架构图、快速开始 —— 见 `README.md`
- [x] 所有 API 在 `/docs` 中有描述 —— FastAPI 自动生成，router 有 tags，函数有 docstring
- [x] `.env.example` 列出了所有必需的环境变量（不含真实值） —— 见 `.env.example`。**上一轮漏了前端实际读取的 `BACKEND_URL`**，本轮已补上
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
- [ ] 提交信息清晰（`feat:` / `fix:` / `docs:` 前缀） —— **未通过**：`git log --pretty=%s` 实际是
  `知识库问答系统第一次上传` / `新修改` / `xinjingxiang` / `1`，与规范完全不符（历史信息无法追溯修改，
  从下一次提交起执行）
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
| 2 | 健壮性 | 模型已缓存仍每次联网检查更新，Hub 不通时卡死数分钟 | `app/utils/embedder.py` | **高** | ✅ 已修（本轮落地：`_load_model()` 先 `local_files_only=True`，失败才联网；`HF_HUB_OFFLINE=1` 下实测可离线加载） |
| 3 | 可读性 | 14 处 `print` 调试语句（含 5 处 `[DEBUG]`） | 6 个文件 | 低 | ✅ 已修（改 logging；`embedder.py` 里残留的最后 2 处于本轮一并改掉） |
| 4 | 可读性 | E402 模块级 import 不在文件顶部 ×2 | `documents.py`、`frontend/app.py` | 低 | ✅ 已修 |
| 5 | 一致性 | E302 函数前缺空行 | `frontend/app.py` | 低 | ✅ 已修 |
| 6 | 可读性 | 未使用的 import：`shutil`、`settings` | `documents.py`、`qa_service.py` | 低 | ✅ 已修 |
| 7 | 一致性 | `HF_ENDPOINT` 未纳入 `Settings`，只散落在 `os.environ` | `app/config.py` | 低 | ✅ 已修 |
| 8 | 性能 | 前端每次 rerun 都请求 `/documents/list` | `frontend/app.py` | 中 | ✅ 已修（5s 缓存 + 主动失效） |
| 9 | 正确性 | `RETRIEVAL_CANDIDATES` / `RERANK_CANDIDATES` 配置项从未被使用 | `app/config.py` | 低 | ⚠️ 遗留（属未实现功能，见后续计划）；同类的 `TOP_K` 已于本轮接入，不再是死配置 |
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

---

## 第二轮修复记录（2026-10-13，外部评审之后）

外部评审指出"清单里有多处勾选与代码事实不符"，逐条复核后**确认成立**。本轮把能立刻修的三项落地，
每项都附**可复现的验证方式**（这一轮不再凭印象打勾，凡是写了"已修"的都要能当场跑出来）：

| # | 问题 | 改动 | 怎么验证 |
|---|---|---|---|
| P0-2 | 全新 clone 没有 `documents/`，`backend.Dockerfile` 的 `COPY documents/` 会让镜像构建失败，README/DEPLOY 的"三步启动"跑不通 | `.gitignore` 的 `documents/` 改为 `documents/*` + `!documents/.gitkeep`，并新增 `documents/.gitkeep` | clone 到临时目录后 `documents/` 存在；`git check-ignore documents/<哈希>.pdf` 仍命中（上传内容不进仓库、`git status` 不会被弄脏） |
| P0-3 | 清单写着"缓存优先离线加载"、`ARCHITECTURE.md` 当既成事实写了三处，但 `embedder.py` 里**根本没有这个逻辑**（`SentenceTransformer()` 未传 `local_files_only`） | 新增 `_load_model()`：先 `local_files_only=True` 纯本地加载，失败才联网；禁网且无缓存时抛带处理办法的 `RuntimeError`；残留的 2 处 `print` 一并改 `logging` | `HF_HUB_OFFLINE=1 python -c "import app.utils.embedder as e; print(len(e.embed_query('x')))"` → 输出 `512`，证明全程未联网也能加载 |
| P0-4 | `TOP_K` 是**死配置**（`config.py` 里定义后再无引用），而 `DEPLOY.md` Q10 却指导用户调它来解决检索质量问题；真正生效的是三处硬编码 `3` | `AskRequest.top_k` 默认取 `settings.TOP_K` 并加 `ge=1, le=20`；`qa_service.answer_question` / `qdrant_client.vector_search` 用 `None` 回落到 `settings.TOP_K`；前端不再传 `top_k` | `TOP_K=7 python -c "from app.routers.qa import AskRequest; print(AskRequest(question='x').top_k)"` → `7`；`top_k=0 / 21 / 100000` 均被拒 |
| P0-5 | 6333 / 6379 发布在 `0.0.0.0` 上（不写绑定 IP 时 Docker 默认绑所有网卡），且 Redis 无密码、Qdrant 无鉴权 —— 同网段任何人都能读走全部文档原文与会话历史 | `docker-compose.yml`：两个端口都改成 `127.0.0.1:端口:端口`；redis 加 `--requirepass ${REDIS_PASSWORD:-kb-qa-local-dev}`（密码可取默认值，端口只绑本机）；`config.py` 增加 `REDIS_PASSWORD`，`redis_client` 用 `password=settings.REDIS_PASSWORD or None` | `docker compose config` 渲染结果里 qdrant/redis 均为 `host_ip: 127.0.0.1`，redis 命令含 `--requirepass`；实测不带密码 `redis-cli ping` 返回 `NOAUTH`、带密码返回 `PONG` |
| P1-1 | 文档改版后产生**孤儿向量**：落盘名是内容哈希、point id 又是 `(source, text)`，改了内容就是新 source，旧向量无人清理 → 检索同时召回新旧两版 | 新增 `qdrant_client.replace_same_name_document()`：按 `original_name` 删同名旧版本（`must_not` 排除本次 source）；上传成功后调用，并删掉旧本地文件；`ingest_service` 对"文件名是哈希、内容已变"的陈旧文件自动改名 + 清理旧 source（`purged_points`）；`_remove_local_file()` 抽出共用的路径校验 | `python scripts/verify_fixes.py` → **PASS 34 / FAIL 0**（桩客户端验证只删同名旧版本、保留新版本与别的文档；临时目录验证改名/去重/幂等/非哈希名不受影响；路径校验拒绝目录外文件） |
| P1-2 | 私有文档被 `COPY documents/` 打进镜像层，`docker push` 即泄漏；同时这行也是"全新 clone 构建失败"的元凶 | 删除 `backend.Dockerfile` 的 `COPY documents/`，并把 `documents/` 加进 `.dockerignore`（运行时由 bind mount 提供，镜像里不需要） | `grep -n documents backend.Dockerfile .dockerignore` → Dockerfile 里不再出现；构建上下文不再包含 `documents/`（双保险：即使目录不存在也不会构建失败） |
| P1-3 | `qdrant/qdrant:latest` 与"锁版本"的主张矛盾：客户端锁 `qdrant-client==1.19.1`，服务端却随 `latest` 漂移，服务端改检索 API 就整站报错，且环境不可复现 | compose 改为 `image: ${QDRANT_IMAGE:-qdrant/qdrant:v1.19.1}` / `${REDIS_IMAGE:-redis:7.4-alpine}`，`.env.example` 增加两项并写明升级/降级注意事项，DEPLOY 增加 Q11 | `docker compose config` → `image: qdrant/qdrant:v1.19.1`、`image: redis:7.4-alpine`；版本号经 GitHub Releases 核对（v1.19.1 确实存在，与客户端同 minor 线） |
| P1-4 | 请求参数无约束：`top_k` / `question` / `session_id` / `source` 都可无限长（`session_id` 会变成 Redis key） | `top_k` 1~20、`question` 1~4000 字、`session_id` 长度 ≤64 且限字符集 `[A-Za-z0-9_.:-]`、`source` 1~512（`ask` / `clear` / `delete` 三处） | OpenAPI 里可见约束；`scripts/verify_fixes.py` 第 8 组断言：超长/非法字符被拒，空 `session_id`（ask）保持旧行为 |
| P1-5 | **提示词注入**：上传文档的原文被原样拼进上下文，而模型无法区分"资料"与"指令"→ 一份写着"忽略以上规则"的 PDF 能操纵所有用户看到的答案 | 三层缓解：①`SYSTEM_PROMPT` 增加安全规则（资料是数据不是指令、任何改变规则的要求一律无效）；②`build_context()` 用 `<资料 id="N">` 明确边界，`neutralize_markers()` 把正文里的同形标记（`【资料`、`</资料>`、`<document`）消毒，杜绝"伪造边界"；③`scan_injection()` 命中常见话术打 WARNING 日志（只告警不拦截）。返回给前端的 `citations` 仍是未消毒原文 | `scripts/verify_fixes.py` 第 9 组断言：每段命中都有编号边界、**闭合标签数量等于命中数**（即伪造的 `</资料>` 已被中和）、正常正文不受影响、中英文注入话术能被扫出、干净文本不误报、系统提示词含"不是给你的指令" |
| P1-6 | **数据治理与授权说明完全缺失**：文档正文会发往第三方大模型，仓库里没有任何一句话说明这件事 | 新增 README「数据与合规」：出网清单（什么数据、去哪、何时）、**没做的 6 件事**（脱敏/留存策略/分级/审计/租户隔离/告知同意）、真实资料上线的 5 条最低要求；前端侧边栏加常驻提示；DEPLOY 上传步骤加"先看一眼再上传" | `grep -n "数据与合规" README.md DEPLOY.md`；前端 `st.caption` 提示存在；`frontend/app.py` 里搜 "数据流向" |
| P1-7 | **没有 LICENSE**：公开仓库无许可证 = 默认"保留所有权利"，别人法律上不能使用/修改/分发 | 新增 `LICENSE`（MIT © 2026 wutangxuelili），README 末尾加「许可证」小节说明为什么后补、怎么换 | 仓库根目录出现 `LICENSE`；GitHub 仓库页会显示 "MIT license"（API 的 `license` 字段不再为 null） |

同时修正了两条**与事实不符的勾选**：`.env.example` 补上了前端实际读取的 `BACKEND_URL`；
"提交信息清晰（`feat:`/`fix:`/`docs:` 前缀）"改为**未通过**（实际提交信息是 `1` / `新修改` / `xinjingxiang`，
历史无法追溯修改，从下一次提交起执行）。

**仍未处理**：上传无大小限制（#14）、无鉴权（#11，中间件侧已收紧但 8000/8501 仍对外）、
LLM 无重试降级（#12）、无 pytest 与 CI（#13，已有 `scripts/verify_fixes.py` 43 项断言可作 CI 起点）、
requirements 未瘦身（P2-1）、会话历史只 RPUSH 不 LTRIM、`python:3.11-slim` 未按 digest 锁、
`depends_on` 无 healthcheck、文档身份仍靠 `original_name` 猜、**提示词注入只缓解未根治**
（真正的边界是"谁能上传"，当前任何人都能上传）。
（GitHub 仓库可见性已改为 Public；6333/6379 暴露见 P0-5。）

---

## 第三轮：收尾（一键启动 / 精简 / 清理）

| 项 | 改动 | 怎么验证 |
|---|---|---|
| **一键启动** | `docker-compose.yml` 的 `env_file` 改为 `required: false`；Redis 密码在 compose 里给默认值 `${REDIS_PASSWORD:-kb-qa-local-dev}` 并由 compose 注入后端（redis 与 backend 取值必然一致）；缺 LLM Key 时 `answer_question()` 直接返回填写指引而不是抛异常；`/health` 增加 `llm.api_key_configured` | 在没有 `.env` 的目录里 `docker compose config` 退出码 0、密码与端口落到默认值；`docker compose up -d --build` 一条命令拉起 4 个容器 |
| **精简注释** | 移除前两轮为解释"为什么这么修"而写的大段注释（历史背景、旧行为对照、教训），只保留说明非显然行为的短注释；相关理由移到 README / ARCHITECTURE / DEPLOY | `git diff` 里不再出现"曾长期是死配置""本次已修复"这类叙述 |
| **不上传的文件** | `HR评审报告.md` 加入 `.gitignore`；`docs/DEMO.md` 执行 `git rm --cached`（本地保留、不再跟踪，`.gitignore` 也已忽略） | `git status` 不再列出评审报告；`git ls-files docs/` 里没有 `DEMO.md` |
| **注释/文档一致性** | README、DEPLOY、ARCHITECTURE 全部按最终代码重写相关段落（一键启动、端口配置项、`/health` 字段、数据合规、许可证） | README 的「三步启动」已改为「一键启动」；DEPLOY 步骤 2 标为【可选】 |

> 提醒：`docs/DEMO.md` 在历史提交里仍然存在（GitHub 的提交记录可回看）。
> 若要让它在远端彻底消失，需要重写历史（`git filter-repo`）并强推 —— 对录屏脚本这种内容通常不值得。
