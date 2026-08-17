# FactorLab · A股多因子研究与样本外回测平台

> **定位**：独立的量化研究项目 — 资产定价 / 因子投资 / 机器学习  
> **目标**：基于 A 股公开数据构建 Value / Quality / Momentum / Volatility / Liquidity 五类因子，以横截面回归、分组组合、Elastic Net、LightGBM **与 PyTorch 深度学习因子模型**互为基线，并通过严格的 expanding-window 样本外（OOS）测试验证因子与模型的稳健性。

> ⚠️ **免责声明**：本项目仅供研究使用，所有产出不构成任何投资建议。市场有风险，投资需谨慎。

---

## 1. 技术栈（重构版 v0.2）

这一版以「工程 + 量化」双高标准重做，技术栈全部升级为当前主流生产级方案：

| 维度 | 选型 |
|---|---|
| 包管理 / 构建 | **uv** + `pyproject.toml`（PEP 621），`hatchling` 构建，锁定 `uv.lock` |
| 配置 | **pydantic-settings** 类型化配置（子模型分域） |
| CLI | **typer** + **rich**，命令：`run` / `serve` / `config` / `version` |
| 数据处理 | **polars** + **duckdb** + pandas/numpy/scipy（列式 + 向量化） |
| 因子模型 | 横截面回归、分组组合、ElasticNetCV、LightGBM/**HistGradientBoosting**，以及 **PyTorch MLP + Optuna HPO** 深度学习因子 |
| 回测与评估 | 自研 expanding-window OOS 引擎；IC / RankIC / IR、分组收益、换手率、最大回撤、交易成本敏感性、牛熊分层稳健性 |
| API 服务 | **FastAPI** + uvicorn，同源托管前端 SPA |
| 前端 | **React 18 + TypeScript + Vite + Tailwind + ECharts**；另提供免构建（CDN）SPA，无需 npm 即可部署 |
| 容器 / CI | **Docker** 多阶段镜像 + `docker-compose`；GitHub Actions（Python 流水线冒烟 + 前端构建产物上传） |
| 文档 | **MkDocs Material**（方法论 / 数据字典 / 快速开始） |

> **为什么有「免构建 SPA」？** 标准 `frontend/` 是完整的 Vite/TS 工程（生产构建产物为 `frontend/dist`）。当 `dist` 不存在时，FastAPI 自动回退托管 `frontend/static-build/`（基于 React UMD + `@babel/standalone` + ECharts CDN），保证任何环境下都能直接打开可用界面，无需 Node 构建步骤，同时显著缩小镜像体积。

### 已移除的 v0.1（legacy）组件
Streamlit 仪表盘（`dashboard/`、`run_dashboard.sh`）、`requirements.txt`、`src/`、`scripts/` 已被 `factorlab/` 包、`pyproject.toml` 与 `config/config.yaml` 取代，已从仓库移除。

---

## 2. 目录结构

```
.
├── README.md
├── LICENSE
├── pyproject.toml                 # uv 托管的项目元数据与依赖
├── uv.lock                        # 锁定依赖
├── config/
│   └── config.yaml                # 所有可调参数（数据/因子/回测/模型/评估/服务）
├── factorlab/                     # 主包（现代工程结构）
│   ├── data/                      # AkShare 加载 / 合成数据 / 清洗 / 交易日历
│   ├── factors/                   # 5 类因子工程
│   ├── models/                    # 截面回归/分组/ElasticNet/LightGBM/deep(PyTorch+Optuna)
│   ├── backtest/                  # OOS expanding-window 回测引擎
│   ├── evaluation/                # IC / 收益 / 换手 / 回撤 / 成本 / 稳健性
│   ├── pipeline.py                # 端到端编排 → 写出 results.json
│   ├── config.py                  # pydantic-settings 类型化配置
│   ├── cli.py                     # typer CLI
│   ├── api/                       # FastAPI 服务（数据 + 触发重算 + 托管 SPA）
│   └── utils/                     # 日志 / IO / 通用
├── frontend/                      # React/TS/Vite 工程（生产构建 → dist）
│   └── static-build/              # 免构建 CDN SPA（无需 npm）
├── docs/                          # MkDocs 文档源
├── outputs/
│   ├── logs/                      # 实验日志（按时间戳）
│   ├── results/                   # results.json 及明细 CSV
│   └── figures/                   # 图表
├── Dockerfile / docker-compose.yml
├── .github/workflows/ci.yml
└── mkdocs.yml
```

---

## 3. 快速开始

### 3.1 环境（uv）

```bash
# 安装依赖（已含 CPU 版 PyTorch / Optuna / LightGBM 等）
uv sync

# 可选：含 AkShare 数据源（联网抓取真实数据）
uv sync --extra data-akshare
```

> 默认运行走**确定性合成数据**（无需联网），适合沙盒自检与 CI；配置 `data.source: akshare` 且 `--data-source akshare` 时尝试真实数据，失败自动回退合成。

### 3.2 运行端到端流水线

```bash
# 默认：eq_weight + elastic_net + lightgbm + deep，HPO 取配置值
uv run factorlab run

# 自定义
uv run factorlab run --models eq_weight,deep --top-k 30 --rebal-freq 21 --cost-bps 20 --hpo 12
```

产出 `outputs/results/results.json`（前端与 API 直接消费）及明细 CSV。

### 3.3 启动服务 + 打开界面

```bash
uv run factorlab serve            # → http://localhost:8000
```

打开 http://localhost:8000 即为研究仪表盘：总览（OOS 净值 + 模型对比）、因子 IC 热力图与衰减、分组收益、牛熊稳健性、交易成本与换手敏感性；右上角可「重新运行流水线」。

### 3.4 API

| 端点 | 说明 |
|---|---|
| `GET /api/health` | 健康检查与可用模型 |
| `GET /api/results` | 全部预计算结果（前端一次性拉取） |
| `GET /api/models` / `/api/nav/{model}` | 模型性能 / 净值序列 |
| `GET /api/ic` / `/api/groups` / `/api/robustness` / `/api/cost-scenarios` / `/api/feature-importance` | 各维度明细 |
| `POST /api/run` | 后台重算（接收模型/TopK/成本/HPO 参数） |
| `GET /api/run/state` | 重算状态轮询 |
| `GET /docs` | Swagger 交互文档 |

---

## 4. 方法论要点

### 4.1 防泄漏（核心）
- **财报可得日期**：所有财务因子强制 `发布日期 ≥ 财报披露截止 + lag_days`，默认 `lag_days=90`（T+90d），杜绝用未来财报预测当期收益。
- **expanding-window OOS**：训练集随时间单调扩大，测试集严格在训练区间之后；绝不允许随机切分或信息泄漏。
- **标签**：T+1 至 T+21 的 21 日累计前向收益（shift -21）。

### 4.2 因子（5 类 16 个）
Value（EP/BP/SP/EP_chg_yoy）、Quality（ROE/ROA/GP_A/Accruals）、Momentum（R_1M/R_3M/R_12_10）、Volatility（Vol_20D/Vol_60D/IdioVol）、Liquidity（Turn_20D/Amihud_20D）。

### 4.3 模型
- **eq_weight**：因子等权合成（经典基线，零过拟合风险）。
- **elastic_net**：带 L1/L2 惩罚的横截面回归（稀疏、稳健）。
- **lightgbm**：梯度提升树；因跨平台 OpenMP 稳定性，macOS 默认回退至算法等价的 `HistGradientBoostingRegressor`，Linux/Docker 用原生 LightGBM。
- **deep**：PyTorch MLP（BatchNorm + Dropout + 早停 + 梯度裁剪），标签标准化；**Optuna TPE** 对隐藏层维度 / dropout / 学习率 / 权重衰减 / batch size 做 HPO，目标为验证集 RankIC。

### 4.4 评估
IC / RankIC / IR、5 分组收益与多空、换手率、最大回撤 / Sharpe / Calmar、交易成本敏感性（0/10/20/30 bps 单边）、牛/震荡/熊市分层稳健性、因子收益衰减。

---

## 5. 部署

```bash
# 构建并启动（多阶段镜像，内部 uv 安装 + 构建前端 dist + factorlab serve）
docker compose up --build
```

镜像内设置 `FACTORLAB_NATIVE_LGB=1`（Linux 用原生 LightGBM），并托管 `frontend/dist`（若存在）。

---

## 6. 复现性

- 合成数据使用**确定性**种子（避免 Python 盐值 `hash()` 跨进程不稳定）。
- 所有随机种子集中在 `config.yaml` 的 `random_seed`。
- 每次运行写入带 UTC 时间戳的日志与可复现的 `results.json`。

---

## 7. 文档

```bash
uv run mkdocs serve     # 本地预览文档站点
```

涵盖：方法论、数据字典、快速开始。
