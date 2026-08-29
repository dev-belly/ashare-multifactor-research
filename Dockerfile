# ========== 阶段 1：构建前端 ==========
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ========== 阶段 2：Python 服务（API + 托管前端） ==========
FROM python:3.11-slim AS backend
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FACTORLAB_NATIVE_LGB=1

# 安装 uv 包管理器
COPY --from=astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
# LightGBM 在 Debian slim 上需要 OpenMP 运行时。
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*
# 先装依赖（利用层缓存）
COPY pyproject.toml uv.lock README.md ./
COPY factorlab ./factorlab
RUN uv sync --no-dev --frozen

# 复制源码与前端产物
COPY factorlab ./factorlab
COPY config ./config
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000
# A fresh image contains no generated research artifact. Build one deterministic,
# lightweight synthetic result on first start so the read-only dashboard is not
# an empty shell; a mounted/persisted results.json is reused on later starts.
CMD ["sh", "-c", "if [ ! -s outputs/results/results.json ]; then uv run factorlab run --data-source synthetic --models eq_weight --hpo 0; fi; exec uv run factorlab serve --host 0.0.0.0 --port 8000"]
