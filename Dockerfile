# ========== 阶段 1：构建前端 ==========
FROM node:24-bookworm-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ========== 阶段 2：Python 服务（API + 托管前端） ==========
FROM python:3.11-slim-bookworm AS backend
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FACTORLAB_NATIVE_LGB=1 \
    PATH="/app/.venv/bin:$PATH"

# 固定 uv 版本，避免 latest 标签造成不可复现构建。
COPY --from=ghcr.io/astral-sh/uv:0.12.4 /uv /uvx /usr/local/bin/

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
COPY config ./config
COPY --from=frontend /frontend/dist ./frontend/dist

# 服务不需要 root 权限。预建可写目录，兼容默认命名卷。
RUN groupadd --gid 10001 factorlab \
    && useradd --uid 10001 --gid factorlab --create-home --shell /usr/sbin/nologin factorlab \
    && mkdir -p outputs/results outputs/logs outputs/figures data/raw data/processed data/factors \
    && chown -R factorlab:factorlab /app/outputs /app/data
USER factorlab

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5m --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=2)" || exit 1
# A fresh image contains no generated research artifact. Build one deterministic,
# lightweight synthetic result on first start so the read-only dashboard is not
# an empty shell; a mounted/persisted results.json is reused on later starts.
CMD ["sh", "-c", "if [ ! -s outputs/results/results.json ]; then factorlab run --data-source synthetic --models eq_weight --hpo 0; fi; exec factorlab serve --host 0.0.0.0 --port 8000"]
