# 数据字典（Data Dictionary）

> 字段含义、口径、单位、来源与可得日期。

---

## 1. 行情数据 (`data/processed/processed.pkl` → `quotes`)

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | index | 交易日（pd.DatetimeIndex） |
| `code` | str | 股票代码（含交易所后缀，如 `600519.SH`） |
| `open`/`high`/`low`/`close` | float | 复权后的开/高/低/收（默认前复权） |
| `volume` | float | 成交量（股） |
| `amount` | float | 成交额（元） |
| `adj_factor` | float | 复权因子 |
| `ret_1d` | float | 当日对数收益（clean 阶段由 `close.pct_change` 计算） |
| `limit_threshold` | float | 涨跌停阈值（默认 10%） |
| `is_limit_up`/`is_limit_down` | bool | 涨停/跌停标记 |
| `is_suspended` | bool | 停牌 / 无成交 / 当日缺失 |

口径：
- 价格以**前复权**为准；
- 停牌日 `close` 用 `ffill` 填充、`volume = 0`；
- 涨跌停阈值对创业板 / 科创板个股自动切换为 20%（生产环境应对接 AkShare 个股 metadata）。

---

## 2. 财务数据 (`financials`)

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | str | 股票代码 |
| `period_end` | date | 报告期（如 2024-09-30） |
| `publish_date` | date | 实际披露日 |
| `available_date` | date | `publish_date + lag_days`（默认 +90d），作为因子"可用日" |
| `revenue` | float | 营业收入 |
| `net_profit` | float | 归母净利润 |
| `equity` | float | 归母股东权益 |
| `total_assets` | float | 总资产 |
| `total_liab` | float | 总负债 |
| `operating_cf` | float | 经营活动现金流 |
| `gross_profit` | float | 毛利 |
| `eps` | float | 每股收益 |
| `bvps` | float | 每股净资产 |
| `shares` | float | 总股本 |

---

## 3. 行业分类 (`industry`)

| 字段 | 类型 | 说明 |
|---|---|---|
| `code` | str | 股票代码 |
| `industry` | str | 申万一级行业（合成数据中是预设枚举） |

---

## 4. 因子面板 (`data/factors/factor_panel.parquet`)

长格式 (MultiIndex `date×code`)，除 `industry`、`is_suspended` 外每列都是一个因子：

### Value（4 个）
| 因子 | 公式 | 备注 |
|---|---|---|
| `ep` | TTM 归母净利 / 总市值 | EP（高 = 低估） |
| `bp` | 归母权益 / 总市值 | BP |
| `sp` | TTM 营收 / 总市值 | SP |
| `ep_chg_yoy` | EP_t − EP_{t-252d} | 同比改善 |

### Quality（4 个）
| 因子 | 公式 | 备注 |
|---|---|---|
| `roe` | TTM 归母净利 / 归母权益 | 净资产收益率 |
| `roa` | TTM 归母净利 / 总资产 | 总资产收益率 |
| `gp_a` | TTM 毛利 / TTM 营收 | 毛利率 |
| `accruals` | (TTM 净利润 − TTM OCF) / 总资产 | 应计利润（负向，值越小越好） |

### Momentum（3 个）
| 因子 | 公式 | 备注 |
|---|---|---|
| `mom_1m` | `close[t] / close[t-21] - 1` | 1 月动量 |
| `mom_3m` | `close[t] / close[t-63] - 1` | 3 月动量 |
| `mom_12_10` | `close[t-21] / close[t-252] - 1` | 经典 12-10 动量 |

### Volatility（3 个）
| 因子 | 公式 | 备注 |
|---|---|---|
| `vol_20d` | −std(returns, 20d) | 20 日收益标准差（负向） |
| `vol_60d` | −std(returns, 60d) | 60 日 |
| `idio_vol` | −std(residuals of 60d rolling beta × market) | 特质波动率 |

### Liquidity（2 个）
| 因子 | 公式 | 备注 |
|---|---|---|
| `turn_20d` | mean(volume, 20d) | 换手率代理 |
| `amihud_20d` | −mean(\|ret\| / amount, 20d) | Amihud 非流动性（负向） |

---

## 5. 评估产出 (`outputs/results/`)

| 文件 | 内容 |
|---|---|
| `factor_ic.csv` | 各因子 IC / RankIC 摘要 |
| `group_ret_<F>.csv` | 因子 F 的 5 分组日收益 |
| `group_perf_summary.csv` | 各因子多空组合年化/Sharpe |
| `nav_<MODEL>.csv` | 模型 OOS 净值 |
| `model_comparison.csv` | 模型对比 |
| `model_perf_summary.csv` | 模型年化/Sharpe/回撤 |
| `robust_regime_<MODEL>.csv` | 模型在不同市场阶段的表现 |
| `market_regime.csv` | 市场牛/熊/震荡标签 |

---

## 6. 图表 (`outputs/figures/`)

| 文件 | 内容 |
|---|---|
| `ic_<F>.png` | 因子 F 的 IC 序列（柱+累积） |
| `group_ret_<F>.png` | 分组 NAV |
| `model_nav.png` | 各模型 OOS NAV 对比 |
| `drawdown.png` | 最大回撤区间 |
| `factor_distribution.png` | 最新截面因子直方图 |
| `turnover_<MODEL>.png` | 调仓日换手 |
