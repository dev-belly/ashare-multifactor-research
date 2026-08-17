#!/usr/bin/env bash
# 启动 Streamlit 仪表盘
set -e
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"

echo "📈 启动 A股多因子研究平台仪表盘 ..."
echo "   浏览器打开: http://localhost:8501"
"$PYTHON_BIN" -m streamlit run dashboard/app.py --server.port 8501
