# A股多因子研究与样本外回测平台

> **项目定位**：独立研究项目 · 资产定价 · 机器学习  
> **研究主题**：基于 A 股公开数据，构建价值/质量/动量/波动率/流动性多因子模型，用横截面回归、分组组合、Elastic Net 与 LightGBM 互为基线，并通过严格的 expanding-window 样本外测试验证因子与模型的稳健性。

---

## 1. 核心目标

1. **统一数据口径**：基于 AkShare 整合 A 股日行情、财务指标、行业分类；统一交易日、复权口径与财报可得日期。
2. **多类因子库**：构建 Value / Quality / Momentum / Volatility / Liquidity 五类因子，并对缺失值、极端值与停牌样本做规则化处理。
3. **严格的样本外验证**：expanding-window 切分 + 财报可得日期偏移，绝不允许随机切分与未来信息泄漏。
4. **模型对比**：横截面回归 / 分组组合 / Elastic Net / LightGBM，比较收益排序能力。
5. **稳健性复核**：评估 IC/RankIC、分组收益、换手率、最大回撤与交易成本敏感性，并按市值、行业与市场阶段做分层复核。
6. **可复现交付**：数据字典、回测脚本、实验日志与图表全部产出。

---

## 2. 目录结构

```
.
├── README.md
├── requirements.txt
├── config/
│   └── config.yaml                # 所有可调参数集中配置
├── data/
│   ├── raw/                       # AkShare 下载的原始数据
│   ├── processed/                 # 清洗后的标准化数据
│   └── factors/                   # 因子矩阵（parquet）
├── src/
│   ├── data/                      # 数据层：AkShare 加载 / 清洗 / 交易日历
│   ├── factors/                   # 因子工程：5 类因子
│   ├── models/                    # 模型：截面回归 / 分组 / Elastic Net / LightGBM
│   ├── backtest/                  # 回测引擎与样本外切分
│   ├── evaluation/                # IC / 收益 / 换手 / 回撤 / 成本 / 稳健性
│   ├── visualization/             # 图表
│   └── utils/                     # 日志 / IO
├── scripts/                       # 入口脚本：fetch → build_factors → run_backtest → evaluate
├── notebooks/                     # 探索性分析
├── outputs/
│   ├── logs/                      # 实验日志（按时间戳）
│   ├── results/                   # 实验结果（CSV / Parquet）
│   └── figures/                   # 图表（PNG / PDF）
└── docs/
    ├── data_dictionary.md         # 数据字典
    └── methodology.md             # 方法论说明
```

---

## 3. 快速开始

### 3.1 环境

```bash
# 推荐 Python 3.10+（项目默认运行时 Python 3.13.12）
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3.2 跑完整流水线

```bash
# 默认走合成数据（无需联网 / 不依赖真实数据），适合沙盒自检
python scripts/05_full_pipeline.py --synthetic

# 真实数据（需要网络 + AkShare 正常返回）
python scripts/05_full_pipeline.py

# 单独跑某一步
python scripts/01_fetch_data.py        --synthetic
python scripts/02_build_factors.py     --input data/processed
python scripts/03_run_backtest.py      --models elastic_net,lightgbm
python scripts/04_evaluate.py          --models all
```

### 3.3 结果查看

跑完会在 `outputs/` 下生成：

- `outputs/logs/exp_<timestamp>.log` — 实验日志
- `outputs/results/factor_ic.csv` — 各因子 IC 序列与统计
- `outputs/results/group_ret_<F>.csv` — 因子 F 的 5 分组收益
- `outputs/results/model_comparison.csv` — 模型对比
- `outputs/results/robust_regime_<M>.csv` — 模型稳健性复核
- `outputs/figures/*.png` — 图表

### 3.4 仪表盘（Web UI）

项目附带一个 Streamlit 仪表盘，覆盖数据概览、因子分析、分组回测、模型对比、稳健性，并可一键运行完整流水线。

```bash
# 方式一：脚本
bash run_dashboard.sh

# 方式二：直接命令
PYTHONPATH=. streamlit run dashboard/app.py
```

打开 http://localhost:8501 即可。界面左侧可调 TopK、调仓频率、交易成本、模型选择、数据源，点击「▶️ 运行完整流水线」即可在界面内重新跑并刷新图表。

---

## 4. 方法论要点

### 4.1 数据
- **交易日对齐**：以沪深交易所交易日为基准，统一复权口径（默认前复权）。
- **财报可得日期**：所有财务因子强制 `发布日期 ≥ 财报披露截止 + lag_days`，默认 `lag_days=90`。
- **缺失 / 极端值 / 停牌**：缺失 → NaN；极端值 → 1%/99% 缩尾；停牌 → 信号冻结。

### 4.2 因子

| 维度 | 示例因子 | 含义 |
|---|---|---|
| Value | EP, BP, SP, E/P2Y | 估值越低越被低估 |
| Quality | ROE, ROA, GP/A, Accruals | 盈利质量越高越优 |
| Momentum | R_1M, R_3M, R_12_10 | 趋势延续 |
| Volatility | Vol_20D, Vol_60D, IdioVol | 低波动异象 |
| Liquidity | Turnover_20D, Amihud | 流动性越好越可交易 |

### 4.3 样本外切分

```
|---train---|--test--|
       |---train---|--test--|
              |---train---|--test--|
```

- **expanding**：每一步训练集不断扩大；
- **永远用 §4.1 的财报可得日期**对齐特征与标签；
- 标签 = T+1 至 T+21 的未来 21 日收益（默认 Next21D_Return）。

### 4.4 评估

- **IC / RankIC**：截面因子值与下期收益相关性；阈值见 `references/quant-factor-research.md`。
- **分组收益**：按因子值分 5 组，最长-最短组的 Spread。
- **换手率**：调仓日持仓变动占比。
- **最大回撤 / 夏普 / Calmar**：组合层面。
- **交易成本敏感性**：0/10/20/30 bps 单边成本。
- **稳健性**：按市值（中/大/小）、行业（中证一级）、市场阶段（Bull/Bear）分层。

---

## 5. 复现性

所有随机种子在 `config.yaml` 的 `random_seed` 集中管理。脚本每次运行：

1. 生成 `outputs/logs/exp_<UTC时间戳>.log`；
2. 关键中间产物以 `parquet` 落盘；
3. 文档化数据版本（合成 / AkShare / Tushare 渠道号）。

---

## 6. 免责声明

> **本项目仅供研究使用，所有产出不构成投资建议**。市场有风险，投资需谨慎。
