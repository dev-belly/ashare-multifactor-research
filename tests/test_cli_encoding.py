from __future__ import annotations

import io

import pytest
from rich.console import Console
from typer.testing import CliRunner

from factorlab import cli


@pytest.mark.parametrize("command", ["run", "report", "serve"])
def test_status_messages_work_with_gbk_output(command, monkeypatch, tmp_path):
    """Redirected Windows output must not fail before the requested action."""
    from factorlab import pipeline, report
    import uvicorn

    buffer = io.BytesIO()
    stream = io.TextIOWrapper(buffer, encoding="gbk")
    console = Console(file=stream, force_terminal=False, legacy_windows=False)
    monkeypatch.setattr(cli, "rprint", console.print)
    called = []

    def action(*args, **kwargs):
        called.append(command)
        return tmp_path / "result.json"

    monkeypatch.setattr(pipeline, "run_pipeline", action)
    monkeypatch.setattr(report, "build_report_from_config", action)
    monkeypatch.setattr(uvicorn, "run", action)
    result = CliRunner().invoke(cli.app, [command])
    assert result.exit_code == 0, result.exception
    assert called == [command]
    stream.flush()
    assert buffer.getvalue().decode("gbk")
