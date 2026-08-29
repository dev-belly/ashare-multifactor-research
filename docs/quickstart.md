# 快速开始

## 1. 安装

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/)；查看 React 前端源码还需要 Node.js。

```bash
git clone https://github.com/dev-belly/ashare-multifactor-research.git
cd ashare-multifactor-research
uv sync
```

## 2. 跑可复现的合成流水线

```bash
uv run factorlab run \
  --data-source synthetic \
  --models eq_weight,elastic_net,lightgbm,deep \
  --hpo 0
```

主要结果写入 `outputs/results/results.json`。默认关闭深度模型 HPO；需要搜索时显式传入例如 `--hpo 8`。

生成单文件研究报告：

```bash
uv run factorlab report
```

报告写入 `outputs/results/report.html`。研究数据内联，但 ECharts 和字体仍通过 CDN 加载。

## 3. 启动只读仪表盘

```bash
uv run factorlab serve
```

打开 <http://localhost:8000>。公开读取端点包括：

| 端点 | 内容 |
| --- | --- |
| `GET /api/results` | 完整预计算结果 |
| `GET /api/models` | 模型绩效概要 |
| `GET /api/nav/{model}` | 指定净值曲线 |
| `GET /api/ic` | IC 与衰减 |
| `GET /api/groups` | 因子分组结果 |
| `GET /api/robustness` | 市况统计 |

浏览器不提供公开重算按钮。若确实需要远程重算，服务端先设置令牌：

```bash
export FACTORLAB_RUN_TOKEN='请替换成长随机密钥'
uv run factorlab serve
```

随后由受信任客户端用 `X-FactorLab-Run-Token` 调用 `POST /api/run`、`GET /api/run/state` 或 `POST /api/reload`。不要把令牌写入网页代码。

## 4. 前端开发

```bash
cd frontend
npm ci --no-audit --no-fund
npm run dev
```

开发服务器默认位于 <http://localhost:5173>，并将 `/api` 代理到后端。

## 5. 实验性 AkShare 模式

```bash
uv sync --extra data-akshare
uv run factorlab run --data-source akshare --models eq_weight --hpo 0
```

严格运行目前会因财务字段不完整而明确失败。只实验真实行情和技术因子时，可在配置中显式启用：

```yaml
data:
  source: akshare
  universe: hs300
  max_symbols: 50
  allow_partial_real_data: true
  allow_fallback: false
```

运行后检查 `meta.actual_data_source`、`meta.fallback_reason` 和 `meta.data_load`。不要把 `akshare_partial` 或降级后的 `synthetic` 当作完整真实数据回测。

## 6. 容器运行

```bash
docker compose up --build
```

首次启动若挂载目录中没有 `results.json`，容器会先生成一个 `eq_weight` 合成数据结果；后续启动复用已保存结果。然后访问 <http://localhost:8000>。

## 7. 验证

```bash
uv sync --frozen --group dev
uv run ruff check --select E4,E7,E9,F factorlab tests
uv run pytest -q
uv run mkdocs build --strict

cd frontend
npm ci --no-audit --no-fund
npm run build
```

!!! warning "免责声明"
    合成数据和历史回测不能预测未来收益，本项目不构成投资建议。
