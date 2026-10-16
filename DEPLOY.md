# 部署指南（DEPLOY.md）

本文面向**第一次拿到这个项目、从没跑过它**的开发者。照着做，10 分钟内能在本机跑起来。

全程只需要 **Docker**，不需要装 Python、不需要懂 Linux。文档里的命令按 **Windows PowerShell** 写，
如果你用 macOS / Linux，只有「激活虚拟环境」那一条命令不同（会单独标注）。

标注说明：

- **【必须】** 缺少这一步项目就跑不起来
- **【可选】** 不做也能跑，只是少了某些能力

---

## 前置要求

### 1. Docker Desktop 【必须】

提供 `docker` 和 `docker compose` 两个命令，Qdrant、Redis、后端、前端四个服务全靠它跑。

**安装**：访问 <https://www.docker.com/products/docker-desktop/> 下载对应系统的安装包，装完**启动 Docker Desktop**。

**版本要求**：Docker 20.10 以上 + 自带 Compose v2（Compose v2 的命令是 `docker compose`，中间是空格，
不是老式的 `docker-compose`）。

**如何验证已安装**：

```powershell
docker --version
docker compose version
```

预期看到两行版本号，例如：

```
Docker version 29.6.2, build dfc4efb
Docker Compose version v5.3.1
```

**还要确认引擎真的在跑**（这一步很多人会漏，装了但没启动照样失败）：

```powershell
docker info
```

预期输出里能找到 `Server Version: ...` 和 `Operating System: Docker Desktop`。
如果报 `error during connect` 或 `Cannot connect to the Docker daemon`，说明 **Docker Desktop 没启动**，
先打开它、等任务栏图标变成稳定状态再重试。

### 2. Git 【必须】

用来把代码拉到本地。

**如何验证已安装**：

```powershell
git --version
```

预期输出形如 `git version 2.43.0.windows.1`。没有的话去 <https://git-scm.com/downloads> 下载安装。

> 如果你拿到的是压缩包（`.zip`）而不是 Git 仓库，这条可以跳过，解压后用「快速开始」的第 2 步继续。

### 3. 一个可用的大模型 API Key 【必须】

系统要靠大模型生成回答。**二选一即可**，不用两个都申请：

| 选项 | 申请地址 | 拿到的变量名 | Key 大致长相 |
|---|---|---|---|
| DeepSeek（默认） | <https://platform.deepseek.com> | `LLM_API_KEY` | `sk-` 开头的一串字符 |
| 通义千问 DashScope | <https://bailian.console.aliyun.com> | `DASHSCOPE_API_KEY` | `sk-` 开头的一串字符 |

**如何验证已获取**：

```powershell
$env:LLM_API_KEY = "刚申请的Key"
curl.exe -s -o NUL -w "%{http_code}`n" https://api.deepseek.com/models -H "Authorization: Bearer $env:LLM_API_KEY"
```

返回 `200` = Key 可用；返回 `401` = Key 填错或已失效；返回 `000` = 网络不通。
验证完请把上面这行清掉（`Remove-Item Env:LLM_API_KEY`），避免 Key 残留在终端历史里。

> DeepSeek 账号需要先在控制台里有一点余额（充值入口在它的「充值」页面），否则调用会返回余额不足。
> 通义千问有免费额度，申请后一般可直接用。

### 4. 磁盘空间 【必须】

建议预留 **10 GB** 以上空闲空间。参考实测值：后端镜像 2.67 GB、前端镜像 801 MB、
Qdrant 数据卷约 621 MB。

**如何验证**：

```powershell
Get-PSDrive -Name C | Select-Object Used, Free
```

看 `Free` 一列，需要大于 10 GB（约 10737418240 字节）。

### 5. 端口 8000 / 8501 / 6333 / 6379 未被占用 【必须】

这四个端口会被本项目占用。**如何验证**（无输出 = 全部空闲）：

```powershell
foreach ($p in 8000,8501,6333,6379) {
  $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
  if ($c) { "$p 被占用" } else { "$p 空闲" }
}
```

### 6. 你不需要额外准备的东西 【重要，避免白费功夫】

- **不需要单独安装 Qdrant 或 Redis**：它们由 Docker 拉起，代码里已经配好。
- **不需要 HuggingFace Token**：向量模型 `BAAI/bge-small-zh-v1.5`（约 95 MB）是公开模型，
  首次使用时会自动下载到 Docker 卷里，不需要登录、不需要 Key。
- **不需要安装 Python**：只有「本地开发模式」才需要（见文末常见问题 Q6）。

---

## 快速开始（10 分钟）

**最省事的路径**：步骤 1 克隆 → 步骤 3 启动，两条命令就完事；步骤 2 的 `.env` 是"想提问时"再补的。

### 步骤 1：克隆仓库 【必须】

```powershell
git clone https://github.com/wutangxuelili/project-zhishiku.git
cd project-zhishiku
```

**预期输出**：`Cloning into 'project-zhishiku'...` 以及下载进度，最后回到命令提示符无报错。

**确认成功**：

```powershell
Get-ChildItem docker-compose.yml, backend.Dockerfile, frontend.Dockerfile
```

应当列出这 3 个文件。

**预计耗时**：10 秒 ~ 1 分钟（取决于网速）。

---

### 步骤 2：创建配置文件 .env 【可选，但想提问就要做】

**先明确一点：不建 `.env` 也能一键启动。** 四个容器会用内置默认值跑起来（Redis 用默认密码
`kb-qa-local-dev`、端口 6333/6379、镜像版本也都有默认值），上传文档、文档管理、检索都能用。
**只有"生成回答"需要大模型 Key** —— 没配 Key 时提问不会报错，界面会直接告诉你该去哪里填。

想开问答就复制模板并填 Key：

```powershell
Copy-Item .env.example .env
notepad .env
```

**要改的地方：大模型 Key。** 把 `sk-请替换成你自己的Key` **整段替换**成你真实的 Key：

```
LLM_API_KEY=sk-请替换成你自己的Key
```

**如果你用的是通义千问**，改两个地方（`LLM_PROVIDER` 改成 `qwen`，并填 `DASHSCOPE_API_KEY`）：

```
LLM_PROVIDER=qwen
DASHSCOPE_API_KEY=sk-请替换成你自己的Key
```

> 顺带说明：`.env.example` 里的 `REDIS_PASSWORD` 留空时，容器会用默认密码
> `kb-qa-local-dev`（Redis 只绑 `127.0.0.1`，仅本机可访问，够用）。
> 若你改过端口绑定、准备给别人访问，务必把它换成一串自己的密码 —— 改完执行
> `docker compose up -d --force-recreate redis backend`，让两个容器拿到同一个新密码。

改完保存并关闭记事本。

**预期输出**：`Copy-Item` 无任何输出即为成功。

**确认成功**（应打印 `True`）：

```powershell
(Select-String -Path .env -Pattern '请替换成你自己的Key' -Quiet) -eq $false
```

`True` 表示你已经把占位符换掉了；如果是 `False`，说明还留着没改的占位符，回去改。

**预计耗时**：1 ~ 2 分钟。

---

### 步骤 3：启动全部服务 【必须】

```powershell
docker compose up -d --build
```

说明：`-d` 表示在后台运行（不占住你的终端），`--build` 表示先构建镜像。

**首次执行会做这几件事**（这就是耗时的地方）：

1. 下载 `qdrant/qdrant:v1.19.1` 和 `redis:7.4-alpine` 两个现成镜像（版本已钉死，见 `.env` 的 `QDRANT_IMAGE` / `REDIS_IMAGE`）
2. 构建后端镜像（要下载 PyTorch 等约 2 GB 的依赖）—— 最慢的一步
3. 构建前端镜像
4. 依次启动 4 个容器

**预期输出**：大量下载/构建日志，最后出现几行 `Container project-zhishiku-xxx-1  Started`。

**预计耗时**：**3 ~ 10 分钟**（首次）。之后再用 `docker compose up -d` 启动是秒级，因为镜像已存在。

**确认成功**：

```powershell
docker compose ps
```

预期看到 **4 个容器**，`STATUS` 列都是 `Up`：

```
NAME                          SERVICE    STATUS         PORTS
project-zhishiku-backend-1    backend    Up 2 minutes   0.0.0.0:8000->8000/tcp
project-zhishiku-frontend-1   frontend   Up 2 minutes   0.0.0.0:8501->8501/tcp
project-zhishiku-qdrant-1     qdrant     Up 2 minutes   127.0.0.1:6333->6333/tcp
project-zhishiku-redis-1      redis      Up 2 minutes   127.0.0.1:6379->6379/tcp
```

> 端口前面有 `127.0.0.1:` 是**故意的**：Qdrant 和 Redis 只允许本机访问（6379 被本机其他程序占用时会显示
> `127.0.0.1:16379->6379/tcp`，见 Q1）。`8000` / `8501` 没有前缀，表示同网络的其他设备也能打开界面。

如果某个容器是 `Exit` 或反复重启，看它的日志（把 `backend` 换成出问题的服务名）：

```powershell
docker compose logs --tail 50 backend
```

---

### 步骤 4：验证后端 【必须】

后端启动时还会做一件事：**首次提问/健康检查会下载向量模型**（约 95 MB），所以第一次访问会偏慢。

最省事的验证方式是直接点开浏览器（比 curl 更直观）：

```powershell
Start-Process http://localhost:8000/docs
```

**预期输出**：浏览器打开 Swagger 页面，标题是「知识库问答系统」，能看到 `/health`、`/qa/ask`、
`/documents/upload` 等接口列表。

**命令行验证**：

```powershell
curl.exe -s http://localhost:8000/health
```

预期返回 JSON，关键是 `"status":"ok"`：

```json
{"status":"ok","qdrant":{"exists":true,"indexed_vectors_count":0,"points_count":0,"status":"green"},
 "embedding":{"model":"BAAI/bge-small-zh-v1.5","dim":512},
 "llm":{"provider":"deepseek","model":"deepseek-chat","api_key_configured":true}}
```

**首次运行会等 30 秒 ~ 2 分钟**（在下载 BGE 模型），之后就是秒回。

> `llm.api_key_configured` 是给你自查用的：`false` 表示还没填 Key —— 此时上传/检索都正常，
> 只有提问会被拒并提示你该填哪个变量。

**看到这些就说明有问题**：

| 现象 | 含义 |
|---|---|
| 连接被拒绝 / 无法访问 | backend 容器没起来，回步骤 3 看日志 |
| `"status"` 不是 `ok` | Qdrant 没连上，检查 qdrant 容器状态 |
| 提问返回 500 | 通常是 `.env` 里 Key 填错或余额不足（没填 Key 不会 500，界面会给提示） |

**预计耗时**：30 秒 ~ 2 分钟（首次，含模型下载）。

---

### 步骤 5：验证前端 【必须】

```powershell
Start-Process http://localhost:8501
```

**预期输出**：浏览器打开页面，标题「📚 知识库问答系统」，左侧是「📁 文档管理」侧边栏，
里面有上传框、「确认上传」、「🔄 重建索引」按钮和「已入库文档」区域，底部有输入框「请输入你的问题...」。

**如果页面一直转圈或显示 `Connection error`**：前端连不上后端，先确认步骤 4 通过；
前端容器内部通过 `http://backend:8000` 访问后端，这个地址由 compose 自动注入，正常不需要你配置。

**预计耗时**：10 ~ 30 秒。

---

### 步骤 6：端到端测试（上传文档 + 提问）【必须】

这一步才真正验证「RAG 全链路」通了。

**6.1 上传一个文件**

仓库自带了示例文档 `test_docs/sample.md`，直接用它最省事。

> ⚠️ **先看一眼再上传**：上传的文档正文会在提问时发送给第三方大模型（DeepSeek / 通义千问）。
> 这一步请只用示例文档或公开资料，别拿涉密/含个人信息的文件试手 —— 详见
> [`README.md` 的「数据与合规」](README.md#数据与合规)。前端侧边栏也有同样的常驻提示。

在步骤 5 打开的页面左侧：

1. 点「上传文档（PDF / Markdown / TXT）」的 **Browse files** 按钮
2. 选择项目里的 `test_docs\sample.md`
3. 点「**确认上传**」按钮
4. 等左下角出现绿色提示：`上传并入库成功：N 个 chunk`

同时「已入库文档」区域会出现 `sample.md (N chunks)`。

**也可以改用命令行上传**（把路径换成你真实的文件路径）：

```powershell
curl.exe -s -X POST http://localhost:8000/documents/upload -F "file=@./test_docs/sample.md"
```

预期返回：

```json
{"message":"上传并入库成功","filename":"xxxx.md","original_name":"sample.md","chunks":8,
 "replaced_chunks":0,"removed_old_files":0}
```

> 重复上传同一个文件不会产生重复数据，会返回 `"文件已存在，已重新入库"`，这是正常的。

**6.2 提一个问题**

在页面底部的输入框「请输入你的问题...」里，针对刚才的文档提问，例如：

```
这份文档讲了什么？
```

按回车。**首次提问会慢**（要加载模型 + 调大模型接口），出现「思考中...」属正常。

**预期输出**：

- 回答里带蓝色引用标记，形如 `[1]` `[2]`
- 回答下方出现可展开的「📖 查看引用来源（N 条）」
- 展开后能看到原文片段、文件名 `sample.md`、相似度分数（如 `0.735`）

**如果回答是 `请求失败：...`**：说明前端调后端失败或大模型 Key 无效，
先看后端日志定位：

```powershell
docker compose logs --tail 50 backend
```

**预计耗时**：1 ~ 3 分钟（首次提问含模型加载）。

---

**走完 6 步，部署就完成了。** 想确认每一步都没漏，用下面的清单逐项打勾。

---

## 验证清单

按顺序打勾，任何一项打不上，看「常见问题」里对应的条目。

- [ ] `docker --version` 和 `docker compose version` 都有版本号输出
- [ ] `docker info` 能看到 `Server Version`（引擎在运行）
- [ ] 已克隆仓库，`docker-compose.yml` 存在
- [ ] `docker compose up -d --build` **一条命令**就把 4 个容器拉起来了（不需要先准备 `.env`）
- [ ] （要开问答才需要）已用 `Copy-Item .env.example .env` 创建 `.env`、填好 Key，
      且**没有任何 `请替换成你自己的Key` 残留**
- [ ] `docker compose ps` 显示 **4 个容器 Up**（qdrant / redis / backend / frontend），
      qdrant / redis 的端口带 `127.0.0.1:` 前缀（6379 被占用时是 `16379`）
- [ ] http://localhost:8000/health 返回 `"status":"ok"`，且 `llm.api_key_configured` 是 `true`
- [ ] http://localhost:8000/docs 能打开 Swagger 接口文档
- [ ] http://localhost:8501 前端页面能打开（不是 Connection error）
- [ ] 上传 `test_docs/sample.md` 后提示「上传并入库成功」，且「已入库文档」里出现该文件（能上传文档）
- [ ] 提问「这份文档讲了什么？」能拿到带 `[1]` 引用的回答，且引用来源可展开（能问答并得到回答）
- [ ] `docker compose logs backend` 里没有 `ERROR` 级别的反复报错

---

## 常见问题

### Q1：启动时报端口被占用（`port is already allocated` / `bind: address already in use`）

**现象**：`docker compose up` 报错，类似
`Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:8501 -> ... address already in use`。

**原因**：8000 / 8501 / 6333 / 6379（或你改过的 `*_HOST_PORT`）中某个端口被别的程序占了
（常见元凶：本机装了原生 Redis 服务占 6379、已有的其他 Web 服务占 8000、另一个 Docker 项目占了同一端口）。

**解决**：先找出是谁占的（把端口号换成报错里的那个）：

```powershell
Get-NetTCPConnection -LocalPort 6379 -State Listen |
  Select-Object LocalPort, OwningProcess,
    @{n='Process';e={(Get-Process -Id $_.OwningProcess).ProcessName}}
```

确认不需要后，二选一：

- 停掉占用进程（在任务管理器里结束它，或 `Stop-Process -Id <PID>`）
- **或者改本项目对外暴露的端口**（推荐，不动别人）：编辑 `docker-compose.yml`，把 `"8000:8000"` 改成 `"18000:8000"`
  （左边是本机端口可随便改，右边是容器内端口**不能改**），然后重新 `docker compose up -d`。
  改完访问地址也相应变成 `http://localhost:18000/docs`。

#### 已实测的坑：本机原生的 Redis 服务占着 6379

Windows 上如果装过 Redis（`Get-Service Redis` 能看到，且 `StartType` 是 `Automatic`），
它会**开机自启并一直占着 127.0.0.1:6379**，Docker 里的 Redis 就再也绑不上，报：

```
Error response from daemon: ports are not available: exposing port TCP 127.0.0.1:6379 -> 127.0.0.1:0:
listen tcp4 127.0.0.1:6379: bind: Only one usage of each socket address ... is normally permitted
```

**光停进程没用**（服务下次开机又起来）。正确做法是让容器用另一个宿主机端口 —— 这两个中间件端口已经做成可配置的，
改 `.env` 即可，**容器内端口始终不变，后端走 compose 内部网络不受影响**：

```
# .env
QDRANT_HOST_PORT=6333
REDIS_HOST_PORT=16379      # 本机 Redis 服务占着 6379，Docker 的 Redis 改用它
```

```powershell
docker compose up -d --force-recreate redis
docker compose ps          # redis 应显示 127.0.0.1:16379->6379/tcp
```

> 如果你确认那个原生服务没用，也可以停掉并禁用自启（需要管理员权限）：
> `Stop-Service Redis; Set-Service Redis -StartupType Disabled`，
> 然后把 `REDIS_HOST_PORT` 改回 `6379`。
>
> ⚠️ **改了端口绑定或密码之后第一次重启**，旧容器可能还占着端口，导致
> `docker compose up -d --force-recreate` 失败。先 `docker compose down`（**不要加 `-v`**，
> 那会删数据卷）把旧容器删干净，再 `docker compose up -d` 就不会撞了。

### Q2：容器起来了，但提问报鉴权错误 / 500

**现象**：前端回答显示 `请求失败：...`，或后端日志出现 `401`、`AuthenticationError`、
`invalid api key`、`Insufficient Balance`。

**原因**：`.env` 里的 Key 没填、填错、填的是占位符原文，或账号余额不足；
也可能是 `LLM_PROVIDER` 与实际填的 Key 不匹配（例如 `LLM_PROVIDER=qwen` 但只填了 `LLM_API_KEY`）。

**解决**：逐项核对 `.env`：

```powershell
Select-String -Path .env -Pattern 'LLM_PROVIDER|LLM_API_KEY|DASHSCOPE_API_KEY'
```

检查要点：

1. `LLM_PROVIDER` 是 `deepseek` 还是 `qwen`，要和下面填的 Key 对应
2. 用 DeepSeek → 必须填 `LLM_API_KEY`；用通义千问 → 必须填 `DASHSCOPE_API_KEY`
3. Key 前后不要加引号、不要留空格，也不要还是 `sk-请替换成你自己的Key`
4. DeepSeek 账号需有余额

改完 `.env` **必须重启后端**才生效：

```powershell
docker compose up -d --force-recreate backend
```

### Q3：报错 `Cannot connect to the Docker daemon` / `docker: command not found`

**现象**：任何 `docker` 命令都失败，提示连不上 daemon 或找不到命令。

**原因**：Docker Desktop 没启动，或命令不在 PATH 里。

**解决**：

1. 确认装没装：`Get-Command docker -ErrorAction SilentlyContinue`
2. 启动 Docker Desktop（开始菜单搜索 Docker Desktop 打开），**等左下角状态变成 Engine running**
3. 再验证：`docker info` 能看到 `Server Version` 就正常了
4. 如果 PowerShell 里始终找不到 `docker`，**关掉当前终端重新开一个**（PATH 变更需要新终端才生效）

> 顺带一提：重启电脑后容器**不会自动拉起**（优雅停止会被视为「手动停止」，
> `restart: unless-stopped` 就不再生效）。数据都还在卷里，重新执行一次 `docker compose up -d` 即可。

### Q4：构建过程中卡住或超时（拉依赖很慢 / `read timeout`）

**现象**：`docker compose up --build` 长时间停在某个 `Downloading ...` 或
`pip install` 步骤，或报 `ReadTimeoutError`、`TLS handshake timeout`、`failed to solve`。

**原因**：需要从境外站点下载 PyPI 包、Docker Hub 镜像和 HuggingFace 模型，网络不稳定时就会超时。
后端镜像要拉的依赖约 2 GB，网络是主要瓶颈。

**解决**（按推荐顺序）：

1. **先重试**：Docker 构建有层缓存，重新执行会从中断处继续，不必从头开始。

   ```powershell
   docker compose up -d --build
   ```

2. **给 Docker 配代理**：Docker Desktop → Settings → Resources → Proxies，
   填上你的 HTTP/HTTPS 代理地址，Apply & Restart 后重试。

3. **给 pip 换国内源**（如果卡在 `pip install` 这一步）：编辑 `backend.Dockerfile`，
   把 `RUN pip install ...` 那一行改成走镜像源，例如加参数
   `-i https://pypi.tuna.tsinghua.edu.cn/simple`，然后重新构建。

4. **模型下载慢**：`.env` 里的 `HF_ENDPOINT` 已默认设为 `https://hf-mirror.com`（国内镜像）。
   如果它反而报 `Distant resource does not seem to be on huggingface.co`，
   说明该镜像做了跨站跳转，把它换回官方端点：

   ```
   HF_ENDPOINT=https://huggingface.co
   ```

   注意 `HF_ENDPOINT` **必须写成纯地址、行尾不要跟注释**，否则注释会被当成地址的一部分。

### Q5：镜像体积太大 / 磁盘不够

**现象**：构建完发现 `docker images` 里后端镜像有好几个 GB，或构建时报 `no space left on device`。

**原因**：后端依赖里包含了 PyTorch。**默认的 PyPI 源会把 CUDA 版 torch 装进来**
（带十几个 `nvidia-*` 显卡运行时包），即使你根本没有显卡、项目也完全用不到 GPU——
这是镜像体积的最大来源。

**解决**：本仓库的 `backend.Dockerfile` 已经是**优化过的 CPU 版多阶段构建**：
builder 阶段显式从 PyTorch 官方 CPU 索引安装 `torch==2.14.0+cpu`，
runtime 阶段只复制 `/root/.local` 里的 Python 包，因此编译工具链和 CUDA 依赖都不会进最终镜像。

实测对比：

| 版本 | DISK USAGE | CONTENT SIZE |
|---|---|---|
| CUDA 版（未优化） | 10.7 GB | 3.51 GB |
| **CPU 版（本仓库当前状态）** | **2.67 GB** | **580 MB** |

如果你看到镜像仍然是 10 GB 级别，说明构建用了旧的 Dockerfile 缓存，强制重建：

```powershell
docker compose build --no-cache backend
docker compose up -d
```

**顺带清理无用空间**（不会删掉正在用的镜像和卷）：

```powershell
docker system prune -f
```

验证当前镜像确实是 CPU 版（预期输出含 `+cpu`）：

```powershell
docker run --rm project-zhishiku-backend python -c "import torch; print(torch.__version__)"
```

> ⚠️ 注意：**不要**用 `docker system prune -a`，`-a` 会删掉所有未使用的镜像，
> 下次启动又得重新构建几 GB。

### Q6：想在本地改代码、不想每次重新构建镜像（本地开发模式）【可选】

**现象**：改一行 Python 代码就要 `docker compose build` 几分钟，太慢。

**原因**：默认是「镜像内跑代码」，改代码不会自动生效。

**解决**：让后端跑在你本机的 Python 里，只用 Docker 起 Qdrant 和 Redis 这两个依赖。
`.env.example` 里 `QDRANT_HOST` / `REDIS_HOST` 默认就是 `localhost`，正是为这个场景准备的。

```powershell
docker compose up -d qdrant redis
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

> macOS / Linux 用户，激活命令换成：`source .venv/bin/activate`

前端另开一个终端：

```powershell
pip install -r frontend/requirements.txt
streamlit run frontend/app.py
```

**注意**：本地模式需要你装好 **Python 3.11**（`python --version` 确认）。
Windows 上如果 `Activate.ps1` 被执行策略拦住，先运行
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`，再重新激活。

### Q7：关于「MCP 子进程启动失败」

**现象**：你在别处见过 `MCP subprocess failed to start` / `McpError` 这类报错，想在这里排查。

**原因与说明**：**本项目不包含任何 MCP 功能**。我全文搜索了仓库（排除 `.venv`/`.git`/`__pycache__`），
`mcp` / `MCP` 关键字**零命中**；代码里没有 MCP 客户端、没有 MCP 服务端、没有相关子进程，
`requirements.txt` 里也没有 `mcp` 依赖。

**解决**：本项目不需要、也不会启动 MCP 子进程，这个报错**不可能来自本项目的部署流程**。
如果你确实遇到了它，它来自你本机另一个工具（例如某个 AI 编辑器/客户端的 MCP 配置），
请到那个工具的配置里排查；本项目的部署不需要做任何与 MCP 相关的操作。

### Q8：`docker: unknown command: docker compose`

**现象**：`docker compose` 报这个错，但 `docker --version` 正常。

**原因**：Docker CLI 找不到 Compose 插件（通常是老版本 Docker Desktop 或 PATH 问题）。

**解决**：

1. 先确认插件目录里有没有它：

   ```powershell
   Get-ChildItem "$env:USERPROFILE\.docker\cli-plugins"
   ```

2. **不要**把 `docker-compose.exe` 复制进这个目录——Docker Desktop 启动时会清理它，重启后就没了。
   正确做法是在 `~/.docker/config.json` 里加 `cliPluginsExtraDirs`，指向 Docker Desktop 自带的插件目录：

   ```jsonc
   {"cliPluginsExtraDirs": ["C:\\Users\\<你>\\AppData\\Local\\Programs\\DockerDesktop\\resources\\cli-plugins"]}
   ```

3. 最省事的办法：**升级到最新版 Docker Desktop**，它自带 Compose v2，装完就有 `docker compose`。

> 环境变量 `DOCKER_CLI_PLUGIN_EXTRA_DIRS` **不是** Docker CLI 支持的选项，设了没用，别绕这个弯路。

### Q9：「已入库文档」是空的，但 `documents/` 目录里明明有文件

**现象**：文件确确实实在 `documents/` 目录下，但前端侧边栏显示「暂无文档」，也搜不到内容。

**原因**：`documents/` 只是**文件存储**，真正的索引在 Qdrant 里。
如果 Qdrant 数据卷被重建过（换机器、执行过 `docker compose down -v`），索引就没了，
文件还在但不在列表里。

**解决**：点前端侧边栏的「**🔄 重建索引**」按钮，把目录里的文档全部重新入库。
或者用命令行：

```powershell
curl.exe -s -X POST http://localhost:8000/documents/reindex
```

预期返回 `{"message":"已重新入库 2 个文件","files":2,"chunks":15,"purged_points":0}`。

### Q10：上传成功但提问回答「无法回答」/ 引用内容不相关

**现象**：文档显示已入库，但提问时模型说找不到相关信息，或引用到明显无关的片段。

**原因**：这是**检索质量问题**，不是部署问题。当前实现是单路向量检索直接取 Top-K，
没有相似度阈值、没有重排——即使命中的片段完全不相关，也会照样塞进上下文。
（`RETRIEVAL_CANDIDATES` / `RERANK_CANDIDATES` 两个配置项在 `.env` 里存在，但代码并未使用。）

**解决**：

- 提高 `TOP_K`：编辑 `.env`，把 `TOP_K=3` 调大到 `5` 或 `8`，然后
  `docker compose up -d --force-recreate backend`。
  检索条数只有这一个来源：接口参数 `top_k` 不传时就取它，前端也不再写死（上限 20，
  防止单个请求把上下文和大模型费用一起放大）
- 提问时更具体一些，并在问题里带上文档里的关键词
- 确认上传的是**文本型 PDF**：扫描件（图片型 PDF）提取不出文字，入不了库；
  可以先用 `test_docs/sample.md` 验证链路本身是通的

### Q11：镜像版本钉死了，启动时报 `manifest unknown` / `not found` / 数据打不开

**背景**：`docker-compose.yml` 里 Qdrant 与 Redis 的镜像都**钉死了版本**
（默认 `qdrant/qdrant:v1.19.1`、`redis:7.4-alpine`），不再用 `latest`。这样"今天能跑、明天服务端偷偷升级导致检索接口变了"这类问题不会发生，但代价是 tag 名必须写对。

**情况 A：报 `manifest unknown`（tag 不存在）**
不同项目 tag 风格不一样（有的带 `v` 有的不带）。先看你本机已有哪个 tag：

```powershell
docker images qdrant/qdrant --format "{{.Repository}}:{{.Tag}}"
```

把结果写进 `.env`（它优先于 compose 里的默认值）：

```
QDRANT_IMAGE=qdrant/qdrant:v1.19.0
```

**情况 B：Qdrant 报存储版本/数据无法打开**
说明你**把服务端降级到了比数据卷更旧的版本**（数据是更高版本写的）。两种办法：

1. 把 `QDRANT_IMAGE` 改成原来那个版本（用上面的 `docker images` 查）；
2. 或者接受重建：`docker compose down -v` 清掉卷，再点「🔄 重建索引」从 `documents/` 恢复
   （原始文档文件在本地磁盘上，不会丢）。

**升级 Qdrant 的正确姿势**：改 `.env` 的 `QDRANT_IMAGE` → 同步升级 `requirements.txt` 里的
`qdrant-client`（两边保持同一条 minor 线）→ 重新构建后端 → 跑一遍上传/提问确认检索正常。

---

## 停止与清理

三个级别，按你的需求选。**命令在项目根目录执行。**

### 级别 1：停止服务，保留数据 【最常用】

```powershell
docker compose stop
```

容器停止但**不删除**。Qdrant 向量数据、Redis 会话、已上传的文档全部保留。
下次 `docker compose up -d` 可以秒起，数据原样还在。

> 如果只是想临时让服务不占端口，用这个。

### 级别 2：停止并删除容器，保留数据

```powershell
docker compose down
```

删除容器和网络，但**数据卷保留**（`qdrant_data` / `redis_data` / `hf_cache` 都还在）。
下次 `up` 会重建容器、挂载原有卷，**文档索引和已下载的模型都不用重新获取**。

### 级别 3：完全清理，连数据一起删 【谨慎】

会**永久删除**所有向量数据、会话历史和已上传的文档，以及缓存的 95 MB 向量模型：

```powershell
docker compose down -v
```

`-v` 就是删卷。执行后：

- Qdrant 里的文档索引全部清空 → 需要重新上传或点「重建索引」
- 首次提问需要重新下载 BGE 模型
- **`documents/` 目录里的原始文件仍然在本地磁盘上**（它是以目录挂载方式进容器的，不在卷里）

**想要更彻底（连本项目镜像一起删）**：

```powershell
docker compose down -v --rmi local
```

`--rmi local` 会删掉本项目自己构建的 `project-zhishiku-backend` 和 `project-zhishiku-frontend` 镜像
（不会删掉 `qdrant/qdrant` 和 `redis` 这两个公共镜像）。
下次启动需要重新构建，**耗时回到 3~10 分钟**。

**确认清理干净**：

```powershell
docker compose ps
docker volume ls | Select-String project-zhishiku
```

两条都应当没有输出（或只剩空标题行）。

---

## 架构速览

一条命令拉起 **4 个容器**。调用链如下（箭头方向 = 谁调用谁）：

```
你的浏览器
   │
   ├─► frontend（Streamlit，容器内 8501）
   │       └─► backend（FastAPI，容器内 8000）
   │                ├─► qdrant（向量库 kb_qa，6333）
   │                └─► redis（会话历史，6379）
   │
   └─► backend 也可以直接从浏览器访问
```

```
backend 还会主动出网访问两个外部服务：
  • DeepSeek / 通义千问 API  ── 生成回答
  • HuggingFace / hf-mirror  ── 首次下载 BGE 模型（约 95 MB，之后走缓存）
```

只有 `backend` 会访问 qdrant 和 redis；`frontend` 不直接连数据库，它只调 backend 的 HTTP 接口。

### 服务与端口对照表

| 服务 | 镜像 / 构建文件 | 容器内端口 | 本机访问地址 | 作用 | 数据持久化 |
|---|---|---|---|---|---|
| `frontend` | `frontend.Dockerfile` | 8501 | http://localhost:8501 | 聊天界面 + 文档管理 | 无（状态在浏览器和 Redis） |
| `backend` | `backend.Dockerfile` | 8000 | http://localhost:8000/docs | FastAPI 接口、RAG 编排 | `documents/` 目录挂载 |
| `qdrant` | `qdrant/qdrant:v1.19.1`（`.env` 的 `QDRANT_IMAGE` / `QDRANT_HOST_PORT` 可覆盖） | 6333 | http://localhost:6333/dashboard（**仅本机**） | 向量数据库 | 卷 `qdrant_data` |
| `redis` | `redis:7.4-alpine`（`.env` 的 `REDIS_IMAGE` / `REDIS_HOST_PORT` 可覆盖） | 6379 | 无需浏览器访问（**仅本机 + 密码**，宿主机端口默认 6379，被占用时改 `REDIS_HOST_PORT`） | 会话历史存储 | 卷 `redis_data` |

#### 端口只绑本机的原因（安全）

`docker-compose.yml` 里 Qdrant 和 Redis 写的是 `"127.0.0.1:6333:6333"` 这种三段的写法。
三段分别是 `绑定IP:宿主机端口:容器端口`；**只写两个数字时 Docker 默认绑 `0.0.0.0`（所有网卡）**，
同一局域网里的别人就能直接 `你的IP:6333` 访问 —— 而 Qdrant 没有鉴权、Redis 那时也没有密码，
等于把全部文档原文和会话历史摆在公网上。现在两者都只绑回环地址：

- 你自己访问 `localhost:6333` / 用 `redis-cli` 连本机：**照常**；
- 别的机器访问你的 `6333` / `6379`：**连不上**（这正是目的）；
- 容器之间（backend → `qdrant:6333` / `redis:6379`）走的是 compose 内部网络，
  **不经过发布端口，完全不受影响** —— 这是最常见的担心，可以放心。

`8000`（后端）和 `8501`（前端）仍然是 `0.0.0.0`，为了方便你用手机或另一台电脑打开界面。
代价是：同一网络里的人也能调用上传/删除接口（项目没有鉴权）。如果你不需要跨设备访问，
把这两行也改成 `"127.0.0.1:8000:8000"` / `"127.0.0.1:8501:8501"` 即可。

### 三个数据卷

| 卷名 | 存什么 | 删掉的后果 |
|---|---|---|
| `project-zhishiku_qdrant_data` | 所有文档向量 | 文档从列表消失，需「重建索引」 |
| `project-zhishiku_redis_data` | 多轮对话历史 | 历史丢失，问答本身不受影响 |
| `project-zhishiku_hf_cache` | 下载好的 BGE 模型（约 95 MB） | 下次提问需重新下载 |

### 一次问答的数据流

1. 浏览器 → `frontend:8501` 输入问题
2. 前端 HTTP POST → `backend:8000` 的 `/qa/ask`
3. 后端从 `redis:6379` 读该会话的历史
4. 用 BGE 模型把问题转向量（512 维，CPU 计算）
5. 到 `qdrant:6333` 的 `kb_qa` 集合做余弦相似度检索，取 Top-K
6. 把命中的片段拼成上下文，连同问题发给 DeepSeek / 通义千问
7. 回答 + 引用来源回传前端；同时把这一轮写回 Redis

---

## 附：一条命令检查整体健康度

部署完成后，想快速确认「一切正常」，复制这一整段到 PowerShell 执行：

```powershell
docker compose ps --format "{{.Service}}`t{{.Status}}"
curl.exe -s http://localhost:8000/health
```

期望：4 个服务都是 `Up`，且第二行 JSON 里 `"status":"ok"`。
