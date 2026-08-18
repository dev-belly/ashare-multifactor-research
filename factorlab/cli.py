"""FactorLab 命令行入口（typer）。

用法：
    factorlab run                      # 运行端到端流水线并生成 results.json
    factorlab run --models eq_weight,deep --top-k 30 --hpo 8
    factorlab serve                   # 启动 FastAPI 服务（默认 :8000）
    factorlab config                  # 打印当前配置
"""
from __future__ import annotations

import typer
from rich import print as rprint

from factorlab.config import Settings
from factorlab.utils.common import PROJECT_ROOT

app = typer.Typer(help="FactorLab · A股多因子研究与样本外回测平台", add_completion=False)


@app.command()
def run(
    config: str = typer.Option(str(PROJECT_ROOT / "config" / "config.yaml"), "--config", "-c", help="配置文件路径"),
    models: str = typer.Option("eq_weight,elastic_net,lightgbm,deep", "--models", "-m", help="逗号分隔的模型"),
    top_k: int = typer.Option(20, "--top-k", help="持仓数量"),
    rebal_freq: int = typer.Option(21, "--rebal-freq", help="调仓频率（交易日）"),
    cost_bps: float = typer.Option(20.0, "--cost-bps", help="单边交易成本（基点）"),
    data_source: str = typer.Option(None, "--data-source", help="data | synthetic"),
    hpo: int = typer.Option(None, "--hpo", help="深度学习 Optuna 超参搜索 trial 数（覆盖配置）"),
):
    """运行端到端流水线（数据→因子→模型→回测→评估）并写出 results.json。"""
    from factorlab.pipeline import run_pipeline

    rprint("[bold green]▶ FactorLab 流水线启动[/bold green]")
    out = run_pipeline(
        config_path=config, models=models, top_k=top_k, rebal_freq=rebal_freq,
        cost_bps=cost_bps, data_source=data_source, hpo_trials=hpo,
    )
    rprint(f"[bold green]✔ 结果已写出：{out}[/bold green]")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h"),
    port: int = typer.Option(8000, "--port", "-p"),
    reload: bool = typer.Option(False, "--reload", help="开发热重载"),
):
    """启动 FastAPI 服务。"""
    import uvicorn

    rprint(f"[bold green]▶ FactorLab API 启动于 http://{host}:{port}[/bold green]")
    uvicorn.run("factorlab.api.main:app", host=host, port=port, reload=reload)


@app.command()
def config():
    """打印当前配置（类型化）。"""
    s = Settings.load()
    rprint(s.model_dump())


@app.command()
def report(
    out: str = typer.Option(None, "--out", "-o", help="报告输出路径，默认 outputs/results/report.html"),
):
    """根据 results.json 生成自包含 HTML 研究报告（可双击打开）。"""
    from factorlab.report import build_report_from_config

    rprint("[bold green]▶ 生成量化研究报告[/bold green]")
    path = build_report_from_config(out_path=out)
    rprint(f"[bold green]✔ 报告已生成：{path}[/bold green]")


@app.command()
def version():
    """打印版本。"""
    rprint("factorlab 0.2.0")


if __name__ == "__main__":
    app()
