# ========== 阶段 1：builder ==========
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .

# 先装 CPU 版 torch（从 PyTorch 官方 CPU 索引）
RUN pip install --user --no-cache-dir torch==2.14.0+cpu \
    --index-url https://download.pytorch.org/whl/cpu

# 再装其余依赖。pip 看到 torch 已装，会跳过 requirements 里的 torch 行
RUN pip install --user --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

# ========== 阶段 2：runtime ==========
FROM python:3.11-slim AS runtime

WORKDIR /app

# 只从 builder 复制 Python 包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# 复制业务代码
COPY app/ ./app/
COPY documents/ ./documents/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]