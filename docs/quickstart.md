# 快速开始

## 1. 环境准备

要求 Python ≥ 3.11 与 [uv](https://github.com/astral-sh/uv)：

```bash
# 安装 uv（如未安装）
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆并进入项目
git clone https://github.com/dev-belly/ashare-multifactor-research.git
cd ashare-multifactor-research

# 安装依赖（自动创建 .venv）
uv sync
```

> 可选：若需接入真实 AkShare 行情，追加 `uv sync --extra data-akshare`。
> 默认使用确定性**合成数据**，无需外网即可完整跑通。

## 2. 运行流水线

```bash
# 端到端：数据 → 因子 → 模型(OOS) → 回测 → 评估
uv run factorlab run

# 指定模型 / 参数 / 开启深度学习 HPO
uv run factorlab run \
  --models eq_weight,elastic_net,lightgbm,deep \
  --top-k 20 --rebal-freq 21 --cost-bps 20 --hpo 8
```

结果写入 `outputs/results/results.json`，供 API 与前端消费。

## 3. 启动服务与界面

```bash
# 启动 FastAPI（默认 :8000），同时托管已构建的前端
uv run factorlab serve
```

浏览器打开 <http://localhost:8000> 即可看到专业深色仪表盘。

前端独立开发模式（热更新）：

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 （/api 自动代理到 :8000）
```

## 4. 容器化部署

```bash
docker compose up --build
# 访问 http://localhost:8000
```

## 5. API 速览

| 端点 | 说明 |
| --- | --- |
| `GET /api/results` | 全部预计算结果（前端一次性拉取） |
| `GET /api/models` | 各模型绩效概要 |
| `GET /api/nav/{model}` | 指定模型净值曲线 |
| `GET /api/ic` | 因子 IC 摘要 + 衰减 |
| `GET /api/groups` | 分组收益 |
| `GET /api/robustness` | 牛/震荡/熊 稳健性 |
| `POST /api/run` | 后台触发重算 |

交互式文档见 <http://localhost:8000/docs>。

!!! note "免责声明"
    本项目仅用于量化研究与教学，所有结果基于合成或历史数据，不构成任何投资建议。
