from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from factorlab.report import build_report


def _pipeline_result_schema() -> dict:
    """A compact fixture matching the dictionary emitted by run_pipeline."""
    series = {"dates": ["2024-01-02", "2024-01-03"], "values": [1.0, 1.025]}
    groups = {f"G{i}": series for i in range(1, 6)}
    perf = {
        "annual_return": 0.12,
        "annual_vol": 0.08,
        "sharpe": 1.5,
        "max_drawdown": -0.04,
        "calmar": 3.0,
    }
    return {
        "meta": {
            "data_source": "synthetic",
            "start_date": "2024-01-02",
            "end_date": "2024-01-03",
            "universe_size": 30,
            "n_factors": 1,
            "models": ["eq_weight"],
            "n_folds": 1,
            "generated_at": "2024-01-04T00:00:00Z",
        },
        "model_nav": {
            "eq_weight": {"nav": series, "perf": perf, "turnover": {"avg": 0.1}}
        },
        "ic_summary": [
            {
                "factor": "ep",
                "method": "spearman",
                "n_periods": 2,
                "ic_mean": 0.03,
                "ic_std": 0.02,
                "ir": 1.5,
                "ic_pos_ratio": 1.0,
                "abs_ic_mean": 0.03,
            }
        ],
        "factor_decay": {
            "ep": [
                {"lag": 1, "ic_mean": 0.04, "ir": 1.2, "n_periods": 2},
                {"lag": 2, "ic_mean": 0.02, "ir": 0.8, "n_periods": 2},
            ]
        },
        "group_returns": {
            "ep": {"groups": groups, "long_short": series, "ls_stats": perf}
        },
        "cost_scenarios": {"0.0": {"eq_weight": perf}, "10.0": {"eq_weight": perf}},
        "robustness": {
            "eq_weight": {
                "bull": perf,
                "neutral": perf,
                "bear": perf,
            }
        },
        "feature_importance": {},
    }


def _inline_report_script(html: str) -> str:
    scripts = html.split("<script>")
    assert len(scripts) == 2
    return scripts[1].split("</script>", 1)[0]


def test_generated_report_executes_with_pipeline_schema(tmp_path: Path) -> None:
    node = shutil.which("node")
    assert node, "Node.js is required to exercise the generated report JavaScript"

    report_path = build_report(_pipeline_result_schema(), tmp_path / "report.html")
    report_script = _inline_report_script(report_path.read_text(encoding="utf-8"))

    harness = r"""
const elements = new Map();
const chartOptions = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {id, innerHTML: '', textContent: ''});
  return elements.get(id);
}
global.window = global;
global.document = {
  getElementById: element,
  querySelector: element,
};
global.addEventListener = () => {};
global.echarts = {
  registerTheme: () => {},
  graphic: {LinearGradient: function () { return {}; }},
  init: (el) => ({
    setOption: (option) => chartOptions.set(el.id, option),
    resize: () => {},
  }),
};
"""
    assertions = r"""
const navOption = chartOptions.get('navChart');
if (!navOption || JSON.stringify(navOption.xAxis.data) !== JSON.stringify(['2024-01-02','2024-01-03'])) {
  throw new Error('NAV dates were not rendered from nav.dates');
}
if (JSON.stringify(navOption.series[0].data) !== JSON.stringify([1,1.025])) {
  throw new Error('NAV values were not rendered from nav.values');
}
const decayOption = chartOptions.get('decayChart');
if (!decayOption || JSON.stringify(decayOption.series[0].data) !== JSON.stringify([[0,0,0.04],[1,0,0.02]])) {
  throw new Error('Decay chart was not rendered from ic_mean');
}
const costOption = chartOptions.get('costChart');
if (!costOption || costOption.series.length !== 1 || JSON.stringify(costOption.series[0].data) !== JSON.stringify([0.12,0.12])) {
  throw new Error('Cost chart did not preserve decimal scenario keys');
}
for (const id of ['navChart','decayChart','groupChart','costChart','robChart']) {
  if (!chartOptions.has(id)) throw new Error(`${id} is blank`);
}
"""

    result = subprocess.run(
        [node, "-e", harness + report_script + assertions],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_report_embeds_results_as_utf8_json(tmp_path: Path) -> None:
    results = _pipeline_result_schema()
    results["meta"]["data_source"] = "合成数据"

    html = build_report(results, tmp_path / "report.html").read_text(encoding="utf-8")

    assert "__DATA__" not in html
    assert json.dumps(results, ensure_ascii=False) in html
