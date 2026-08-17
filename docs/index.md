# FactorLab · A股多因子研究与样本外回测平台

> 一个工程化、可复现、样本外严格的 A 股多因子研究平台：
> 因子工程 → 多模型（线性 / 树模型 / **深度学习**）→ expanding-window 样本外回测 → 多维度稳健性评估 → 服务化与可视化。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 语言 / 包管理 | Python 3.11 + [uv](https://github.com/astral-sh/uv) |
| 配置 | pydantic-settings（类型化 YAML） |
| 命令行 | typer + rich |
| 数据处理 | pandas / numpy / polars / duckdb |
| 因子模型 | OLS / ElasticNet / LightGBM（GBDT）/ **PyTorch MLP + Optuna HPO** |
| 回测框架 | expanding-window 样本外，财报 T+90d 防泄漏 |
| 评估 | IC / RankIC / IR、分组组合、交易成本敏感性、牛熊稳健性 |
| 服务端 | FastAPI + Uvicorn |
| 前端 | React + TypeScript + Vite + TailwindCSS + ECharts |
| 部署 | Docker / docker-compose |
| 文档 / CI | MkDocs Material / GitHub Actions |

## 架构总览

```
AkShare / 合成数据
        │
        ▼
factorlab.data       数据加载 + 清洗 + 日历对齐
factorlab.factors    5 大类 16 因子 + 截面标准化/中性化
factorlab.models     交叉回归 / ElasticNet / LightGBM / 深度学习
factorlab.backtest   expanding-window OOS + 成本模型 + 引擎
factorlab.evaluation IC / 分组 / 换手 / 稳健性
factorlab.pipeline   端到端编排 → outputs/results/results.json
        │
        ├─► FastAPI (factorlab.api)  ──► React 仪表盘
        └─► typer CLI (factorlab.cli)
```

## 核心特性

- **样本外严谨性**：严格 expanding-window 切分，训练只用"已发布"财务因子；默认财报可得日滞后 90 天，杜绝未来函数。
- **多模型对比**：从线性组合到梯度提升树，再到神经网络，统一接口、统一回测。
- **深度学习因子**：PyTorch MLP 横截面收益预测，内置 Optuna 超参搜索（隐藏层、Dropout、学习率、权重衰减）。
- **可复现**：合成数据确定性生成（无盐值 hash），随机种子集中管理。
- **工程化**：uv 依赖锁、类型化配置、CLI、API、容器化、CI、文档一应俱全。

## 快速链接

- [快速开始](quickstart.md)
- [方法论](methodology.md)
- [因子字典](data_dictionary.md)
