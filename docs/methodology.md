# 方法论说明（Methodology）

## 1. 数据流程

```
AkShare / Synthetic
      │
      ▼
  raw quotes / financials / industry
      │
      │  ┌── 复权 → 缺失 → 停牌标记 → 标签 (ret_1d)
      ├──┤
      │  └── 财报对齐 (publish_date + lag)
      ▼
   因子面板（截面 + 时序）
      │
      ├── 缩尾 (winsorize 1%/99%)
      ├── 行业内 zscore（行业中性化）
      ├── 全截面 zscore / rank
      └── 缺失样本剔除（停牌 / ST）
      │
      ▼
  截面因子面板 (date × code × factors)
```

## 2. 样本外（OOS）切分

- **expanding window**：每折的训练集只扩大、不缩回。
- 测试期长短 = 1 年（与再调频率一致可减少 overlap 偏误）。
- 在每折内部：
  1. 在 `[train_start, train_end)` 上训练模型；
  2. 在 `[test_start, test_end)` 上预测下期分数；
  3. 调仓用预测分数构造多头组合；
  4. 跟踪日收益 → 累计净值。
- 关键：**所有训练特征必须用 `available_date ≤ train_end`** 之后的最新可用财务值；
  - 实现方式：财务面板的列已按 `available_date = publish_date + 90d` 对齐到日历，
    OOS 切分时只取 `date ∈ [train_start, train_end)`；这天然屏蔽了"未来披露才有的财务"。

## 3. 模型方法

### 3.1 横截面回归（Fama-MacBeth）
- 每期 t 用 `(X_t, y_t)` OLS 得 beta_t；
- 累计所有 beta 求 t 统计量（F-M 检验）；
- 预测时用平均 beta 对未来 X 加权得到 score。

### 3.2 分组组合（Sort Portfolio）
- 按因子值排序，每期分 N 组（默认 5）；
- 组内等权，得到每组日收益；
- 多空组 = (G_max − G_min)。

### 3.3 Elastic Net
- sklearn `ElasticNetCV`，5 折 CV 选 (alpha, l1_ratio)；
- 在每个训练折上拟合，对 OOS 期预测 → score。

### 3.4 LightGBM
- n_estimators=200, lr=0.05, num_leaves=31, L1=0.1, L2=0.1；
- 输出 importance 用于事后解释；
- 沙盒若无 lightgbm，自动降级到 `HistGradientBoosting`。

## 4. 评估指标

| 类别 | 指标 | 阈值 / 解释 |
|---|---|---|
| 预测力 | IC = corr(score, y) | \|IC\| > 0.03 基本；> 0.05 强 |
| | RankIC = corr(rank, rank) | 同上，对异常更稳健 |
| | IR = mean(IC) / std(IC) | > 0.5 稳定；> 1.0 复核 |
| 收益 | 年化 / Sharpe / Calmar | 与基准对比 |
| 风控 | 最大回撤 | 越小越稳健 |
| 交易 | 换手率（年均） | 越高成本越敏感 |
| 成本 | 单边 0/10/20/30 bps | 表 + 图 |
| 稳健性 | 按 cap / 行业 / 阶段 | 防止伪 alpha |

### 4.1 单因子有效性阈值（来自 `references/quant-factor-research.md`）
- IC > 0.03 且 IR > 0.5 才考虑入组合；
- IC > 0.1 需检查 look-ahead bias；
- IR > 1.0 极罕见，需复核。

## 5. 避坑清单

| 风险 | 防御 |
|---|---|
| **前向偏差** | 财务 lag + OOS 时间切分 |
| **生存偏差** | 上市未满 N 月的股票默认剔除（生产环境可加） |
| **行业偏见** | 行业内 zscore 中性化 |
| **极值主导** | 缩尾 + zscore |
| **停牌虚假成交** | 标记 + 因子置 NaN |
| **涨跌停不能成交** | 回测时禁止换股 |
| **随机切分泄漏** | 仅 expanding window |

## 6. 复现性

- 全部随机种子集中在 `config.yaml` 的 `random_seed`；
- 合成数据生成器也使用固定 seed；
- 实验日志带 UTC 时间戳（`outputs/logs/exp_<UTC>.log`）。

## 7. 已知限制

- 真实环境需接入 Tushare / Wind 等更稳定的财务接口；
- AkShare 在沙盒中可能因网络问题失败，本项目默认降级到合成数据；
- 行业中性化用申万一级；切换中证一级需修改 `industry_neutralize` 的分组键；
- 涨跌停阈值未对创业板 / 科创板个股区分（生产应做）。
