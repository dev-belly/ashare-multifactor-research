# 数据与输出字典

## 1. 行情数据

每只股票是一张以 `date` 为索引的表：

| 字段 | 类型 | 当前口径 |
| --- | --- | --- |
| `open` / `high` / `low` / `close` | float | 合成 OHLC 或 AkShare 前复权行情 |
| `volume` | float | 成交量 |
| `amount` | float | 成交额；部分因子允许缺失 |
| `adj_factor` | float | 当前加载器中的兼容字段 |
| `ret_1d` | float | `close.pct_change()` 的简单收益，不是对数收益 |
| `limit_threshold` | float | 当前统一近似为 10% |
| `is_limit_up` / `is_limit_down` | bool | 基于上述近似阈值的标记 |
| `is_suspended` | bool | 成交量为 0、价格缺失或日历补齐形成的停牌标记 |

日历对齐会向前填充 OHLC、把缺失成交量补为 0。当前回测尚未根据涨跌停和停牌标记阻止成交，不能把这些标记误解为完整的成交约束模型。

## 2. 财务数据

| 字段 | 含义 |
| --- | --- |
| `code` | 带交易所后缀的股票代码 |
| `period_end` | 报告期末 |
| `publish_date` | 披露日 |
| `available_date` | `publish_date + financial_lag_days`，在因子构建时生成 |
| `revenue` | 营业收入 |
| `net_profit` | 归母净利润 |
| `equity` | 归母权益 |
| `total_assets` / `total_liab` | 总资产 / 总负债 |
| `operating_cf` | 经营活动现金流 |
| `gross_profit` | 毛利 |
| `shares` | 总股本；按可得日向后对齐 |

合成数据还提供 `eps` 和 `bvps`。AkShare 的这些时点字段尚未完成标准化，所以严格实数模式不会假装拥有完整财务数据。

## 3. 行业数据

| 字段 | 含义 |
| --- | --- |
| `code` | 股票代码 |
| `industry` | 行业名称；缺失时使用 `Unknown` |

行业用于行业内标准化。AkShare 覆盖率会记录在 `meta.data_load.data_components.industry`。

## 4. 因子面板

索引为 `(date, code)`，元数据列为 `industry` 和 `is_suspended`；其余可用列为因子：

| 类别 | 因子 | 简化口径 |
| --- | --- | --- |
| Value | `ep`, `bp`, `sp` | 时点财务值 / 当日市值 |
| Value | `ep_chg_yoy` | 当前 EP 与约 252 个交易日前 EP 之差 |
| Quality | `roe`, `roa`, `gp_a`, `accruals` | 盈利能力与应计质量 |
| Momentum | `mom_1m`, `mom_3m`, `mom_12_10` | 21 日、63 日、跳过最近月的长周期动量 |
| Volatility | `vol_20d`, `vol_60d`, `idio_vol` | 负向波动与特质波动 |
| Liquidity | `turn_20d` | 20 日平均 `volume / 最新已披露 shares` |
| Liquidity | `amihud_20d` | 负的 20 日平均 `abs(return) / amount` |

缩尾、行业内标准化和全截面标准化在每个交易日独立进行。

## 5. `results.json`

当前流水线实际写出两个用户可见文件：

| 文件 | 内容 |
| --- | --- |
| `outputs/results/results.json` | 结构化研究结果 |
| `outputs/results/report.html` | 由上述 JSON 生成的浏览器报告 |

`results.json` 顶层字段：

| 字段 | 内容 |
| --- | --- |
| `meta` | 数据来源、覆盖率、日期、模型、fold、标签与执行参数 |
| `model_nav` | `benchmark` 与成功模型的净值、绩效和换手 |
| `cost_scenarios` | 各策略在不同单边 bps 下的绩效 |
| `ic_summary` | 因子 Pearson/Spearman IC 摘要 |
| `group_returns` | Top 因子的分组净值与多空统计 |
| `factor_decay` | 因子不同 lag 的 IC 摘要 |
| `robustness` | 按市场阶段统计的结果 |
| `feature_importance` | 可用时的模型特征重要性 |

不可表示的非有限浮点数会序列化为 JSON `null`，不会输出非标准 `NaN` 或 `Infinity`。
