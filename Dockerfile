# ========== 阶段 1：构建前端 ==========
FROM node:20-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install --no-audit --no-fund
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
# 先装依赖（利用层缓存）
COPY pyproject.toml ./
COPY factorlab ./factorlab
RUN uv sync --no-dev --frozen || uv sync --no-dev

# 复制源码与前端产物
COPY factorlab ./factorlab
COPY config ./config
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["uv", "run", "factorlab", "serve", "--host", "0.0.0.0", "--port", "8000"]
