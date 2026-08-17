import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import { fetchResults, triggerRun, fetchRunState, RunParams } from "./api";
import { Results, IcRow, Meta } from "./types";

const MODEL_COLORS: Record<string, string> = {
  eq_weight: "#3b82f6",
  elastic_net: "#22c55e",
  lightgbm: "#f59e0b",
  deep: "#a855f7",
  cross_section: "#06b6d4",
};

const fmtPct = (v?: number) =>
  v === undefined || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(1)}%`;
const fmtNum = (v?: number, d = 2) =>
  v === undefined || Number.isNaN(v) ? "—" : v.toFixed(d);

type Tab = "overview" | "ic" | "groups" | "robustness" | "cost";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="stat-value mt-1">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function PerfTable({ results }: { results: Results }) {
  const rows = Object.entries(results.model_nav).map(([name, m]) => ({ name, perf: m.perf }));
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="text-slate-400 bg-ink-700/50">
          <tr>
            <th className="text-left px-4 py-2">模型</th>
            <th className="text-right px-4 py-2">年化收益</th>
            <th className="text-right px-4 py-2">年化波动</th>
            <th className="text-right px-4 py-2">Sharpe</th>
            <th className="text-right px-4 py-2">最大回撤</th>
            <th className="text-right px-4 py-2">Calmar</th>
            <th className="text-right px-4 py-2">累计收益</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-t border-ink-600/40">
              <td className="px-4 py-2 font-medium">
                <span
                  className="inline-block w-2 h-2 rounded-full mr-2"
                  style={{ background: MODEL_COLORS[r.name] || "#888" }}
                />
                {r.name}
              </td>
              <td className="text-right px-4 py-2 font-mono text-bull">{fmtPct(r.perf.annual_return)}</td>
              <td className="text-right px-4 py-2 font-mono">{fmtPct(r.perf.annual_vol)}</td>
              <td className="text-right px-4 py-2 font-mono text-accent-glow">{fmtNum(r.perf.sharpe)}</td>
              <td className="text-right px-4 py-2 font-mono text-bear">{fmtPct(r.perf.max_drawdown)}</td>
              <td className="text-right px-4 py-2 font-mono">{fmtNum(r.perf.calmar)}</td>
              <td className="text-right px-4 py-2 font-mono text-bull">{fmtPct(r.perf.total_return)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function NavChart({ results }: { results: Results }) {
  const series = Object.entries(results.model_nav).map(([name, m]) => ({
    name,
    type: "line",
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 2 },
    itemStyle: { color: MODEL_COLORS[name] || "#888" },
    data: m.nav.dates.map((d, i) => [d, m.nav.values[i]]),
  }));
  const option: any = {
    backgroundColor: "transparent",
    grid: { left: 50, right: 20, top: 40, bottom: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: {
      type: "time",
      axisLine: { lineStyle: { color: "#2a3650" } },
      axisLabel: { color: "#7e93ad" },
    },
    yAxis: {
      type: "value",
      name: "净值",
      nameTextStyle: { color: "#7e93ad" },
      splitLine: { lineStyle: { color: "#1a2233" } },
      axisLabel: { color: "#7e93ad" },
    },
    series,
  };
  return <ReactECharts option={option} style={{ height: 380 }} notMerge />;
}

function IcHeatmap({ ic }: { ic: IcRow[] }) {
  const factors = Array.from(new Set(ic.map((r) => r.factor)));
  const methods = Array.from(new Set(ic.map((r) => r.method)));
  const data: [number, number, number][] = ic.map((r) => [
    methods.indexOf(r.method),
    factors.indexOf(r.factor),
    Number((r.ir || 0).toFixed(3)),
  ]);
  const option: any = {
    backgroundColor: "transparent",
    grid: { left: 90, right: 20, top: 20, bottom: 40 },
    tooltip: { position: "top", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    xAxis: { type: "category", data: methods, axisLabel: { color: "#9fb3cc" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "category", data: factors, axisLabel: { color: "#9fb3cc" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    visualMap: { min: -1, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 0, inRange: { color: ["#22c55e", "#0f1623", "#ef4444"] }, textStyle: { color: "#9fb3cc" } },
    series: [{ type: "heatmap", data, label: { show: true, color: "#e5edf7", fontSize: 10 }, emphasis: { itemStyle: { borderColor: "#fff", borderWidth: 1 } } }],
  };
  return <ReactECharts option={option} style={{ height: 460 }} notMerge />;
}

function DecayChart({ decay }: { decay: Record<string, any[]>; factor: string }) {
  const rows = decay[factor] || [];
  const option: any = {
    backgroundColor: "transparent",
    grid: { left: 50, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "category", data: rows.map((r) => r.lag), name: "lag(日)", axisLabel: { color: "#7e93ad" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "value", name: "RankIC", axisLabel: { color: "#7e93ad" }, splitLine: { lineStyle: { color: "#1a2233" } } },
    series: [
      { name: "IC均值", type: "line", smooth: true, data: rows.map((r) => r.ic_mean), itemStyle: { color: "#3b82f6" }, areaStyle: { color: "rgba(59,130,246,0.12)" } },
      { name: "IR", type: "line", smooth: true, data: rows.map((r) => r.ir), itemStyle: { color: "#f59e0b" } },
    ],
  };
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />;
}

function GroupChart({ group }: { group: any }) {
  const keys = Object.keys(group.groups || {});
  const series = keys.map((k) => ({
    name: k,
    type: "line",
    showSymbol: false,
    smooth: true,
    data: group.groups[k].dates.map((d: string, i: number) => [d, group.groups[k].values[i]]),
    itemStyle: { color: k === keys[keys.length - 1] ? "#ef4444" : k === keys[0] ? "#22c55e" : undefined },
  }));
  series.push({
    name: "多空",
    type: "line",
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 3, type: "dashed" },
    data: group.long_short.dates.map((d: string, i: number) => [d, group.long_short.values[i]]),
    itemStyle: { color: "#a855f7" },
  });
  const option: any = {
    backgroundColor: "transparent",
    grid: { left: 50, right: 20, top: 40, bottom: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "time", axisLabel: { color: "#7e93ad" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "value", name: "净值", axisLabel: { color: "#7e93ad" }, splitLine: { lineStyle: { color: "#1a2233" } } },
    series,
  };
  return <ReactECharts option={option} style={{ height: 360 }} notMerge />;
}

function RobustTable({ results }: { results: Results }) {
  const models = Object.keys(results.robustness || {});
  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="text-slate-400 bg-ink-700/50">
          <tr>
            <th className="text-left px-4 py-2">模型</th>
            <th className="text-right px-4 py-2">牛市 年化</th>
            <th className="text-right px-4 py-2">震荡 年化</th>
            <th className="text-right px-4 py-2">熊市 年化</th>
            <th className="text-right px-4 py-2">牛/熊 Sharpe</th>
          </tr>
        </thead>
        <tbody>
          {models.map((m) => {
            const r = results.robustness[m];
            return (
              <tr key={m} className="border-t border-ink-600/40">
                <td className="px-4 py-2 font-medium">
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: MODEL_COLORS[m] || "#888" }} />
                  {m}
                </td>
                <td className="text-right px-4 py-2 font-mono text-bull">{fmtPct(r.bull?.annual_return)}</td>
                <td className="text-right px-4 py-2 font-mono">{fmtPct(r.neutral?.annual_return)}</td>
                <td className="text-right px-4 py-2 font-mono text-bear">{fmtPct(r.bear?.annual_return)}</td>
                <td className="text-right px-4 py-2 font-mono">
                  {fmtNum(r.bull?.sharpe)} / {fmtNum(r.bear?.sharpe)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CostChart({ results }: { results: Results }) {
  const costs = Object.keys(results.cost_scenarios || {});
  const models = Object.keys(results.cost_scenarios?.[costs[0]] || {});
  const series = models.map((m) => ({
    name: m,
    type: "line",
    smooth: true,
    symbol: "circle",
    data: costs.map((c) => results.cost_scenarios[c][m]?.annual_return ?? null),
    itemStyle: { color: MODEL_COLORS[m] || "#888" },
  }));
  const option: any = {
    backgroundColor: "transparent",
    grid: { left: 55, right: 20, top: 40, bottom: 40 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "category", data: costs.map((c) => `${c}bps`), name: "单边成本", axisLabel: { color: "#7e93ad" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "value", name: "年化收益", axisLabel: { color: "#7e93ad", formatter: (v: number) => `${(v * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: "#1a2233" } } },
    series,
  };
  return <ReactECharts option={option} style={{ height: 320 }} notMerge />;
}

export default function App() {
  const [results, setResults] = useState<Results | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [factor, setFactor] = useState<string>("");
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState<string>("");

  const load = () => {
    fetchResults()
      .then((r) => {
        setResults(r);
        setError(null);
        if (!factor && r.group_returns) setFactor(Object.keys(r.group_returns)[0] || "");
      })
      .catch((e) => setError(String(e)));
  };

  useEffect(() => {
    load();
    const t = setInterval(() => {
      fetchRunState().then((s) => {
        if (s.running && !running) setRunning(true);
        if (!s.running && running) {
          setRunning(false);
          load();
        }
      });
    }, 4000);
    return () => clearInterval(t);
  }, []);

  const onRun = async () => {
    setRunning(true);
    setRunMsg("流水线后台重算中…");
    const params: RunParams = { models: results?.meta.models?.join(","), hpo: results?.meta.hpo_trials || 0 };
    try {
      await triggerRun(params);
    } catch (e) {
      setRunMsg("触发失败：" + String(e));
      setRunning(false);
    }
  };

  const meta: Meta = results?.meta || {};
  const topFactors = useMemo(() => {
    if (!results) return [];
    return Array.from(new Set(results.ic_summary.map((r) => r.factor)));
  }, [results]);

  if (error && !results) {
    return (
      <div className="p-10">
        <div className="card p-6 text-center">
          <div className="text-bull text-lg">无法加载结果数据</div>
          <div className="text-slate-400 mt-2">{error}</div>
          <div className="text-slate-500 mt-3 text-sm">
            请先运行 <code className="pill">factorlab run</code> 生成 outputs/results/results.json，
            或启动 <code className="pill">factorlab serve</code>。
          </div>
        </div>
      </div>
    );
  }

  if (!results) {
    return (
      <div className="p-10 flex items-center justify-center h-full">
        <div className="text-accent-glow animate-pulse text-lg">加载中…</div>
      </div>
    );
  }

  const tabs: { key: Tab; label: string }[] = [
    { key: "overview", label: "总览" },
    { key: "ic", label: "因子 IC" },
    { key: "groups", label: "分组收益" },
    { key: "robustness", label: "稳健性" },
    { key: "cost", label: "成本与换手" },
  ];

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-10 border-b border-ink-600/60 bg-ink-900/80 backdrop-blur">
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-accent to-purple-500 flex items-center justify-center font-bold text-white">F</div>
            <div>
              <div className="text-lg font-semibold tracking-tight">FactorLab</div>
              <div className="text-xs text-slate-400">A股多因子研究 · 样本外回测 · 深度学习因子</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {running ? (
              <span className="pill text-accent-glow">● 重算中</span>
            ) : (
              <span className="pill text-emerald-400">● 就绪</span>
            )}
            <button
              onClick={onRun}
              disabled={running}
              className="rounded-lg bg-accent/90 hover:bg-accent px-3 py-1.5 text-sm font-medium disabled:opacity-40 transition"
            >
              重新运行流水线
            </button>
          </div>
        </div>
        <nav className="px-6 flex gap-1 border-t border-ink-700/60">
          {tabs.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`px-4 py-2 text-sm border-b-2 transition ${
                tab === t.key ? "tab-active" : "text-slate-400 border-transparent hover:text-slate-200"
              }`}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="flex-1 px-6 py-5">
        <div className="flex flex-wrap gap-3 mb-5">
          <Stat label="样本区间" value={`${meta.start_date} ~ ${meta.end_date}`} />
          <Stat label="股票数" value={String(meta.universe_size ?? "—")} sub={`${meta.n_factors} 个因子`} />
          <Stat label="OOS 折数" value={String(meta.n_folds ?? "—")} sub={`持仓 ${meta.top_k} · 调仓 ${meta.rebal_freq}日`} />
          <Stat label="数据源" value={meta.data_source ?? "—"} sub={meta.deep_enabled ? "含深度学习模型" : ""} />
          <Stat label="生成时间" value={(meta.generated_at || "").replace("T", " ").slice(0, 16)} />
        </div>

        {tab === "overview" && (
          <div className="space-y-5">
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">样本外净值曲线（基准=1.0）</div>
              <NavChart results={results} />
            </div>
            <PerfTable results={results} />
          </div>
        )}

        {tab === "ic" && (
          <div className="space-y-5">
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">因子 IC / RankIC 信息比率（热力图）</div>
              <IcHeatmap ic={results.ic_summary} />
            </div>
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">因子收益衰减（RankIC 随持有期衰减）</div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs text-slate-400">因子：</span>
                <select
                  value={factor}
                  onChange={(e) => setFactor(e.target.value)}
                  className="bg-ink-700 border border-ink-500 rounded px-2 py-1 text-sm"
                >
                  {topFactors.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <DecayChart decay={results.factor_decay} factor={factor} />
            </div>
          </div>
        )}

        {tab === "groups" && (
          <div className="space-y-5">
            <div className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-slate-300 font-medium">分组净值（G1 最低 → G5 最高，虚线为多空）</div>
                <select
                  value={factor}
                  onChange={(e) => setFactor(e.target.value)}
                  className="bg-ink-700 border border-ink-500 rounded px-2 py-1 text-sm"
                >
                  {topFactors.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              {results.group_returns[factor] && <GroupChart group={results.group_returns[factor]} />}
              {results.group_returns[factor] && (
                <div className="text-xs text-slate-400 mt-2">
                  多空组合：年化 {fmtPct(results.group_returns[factor].ls_stats.annual_return)} · Sharpe{" "}
                  {fmtNum(results.group_returns[factor].ls_stats.sharpe)} · 最大回撤{" "}
                  {fmtPct(results.group_returns[factor].ls_stats.max_drawdown)}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "robustness" && (
          <div className="space-y-5">
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">牛 / 震荡 / 熊 市表现（按市场阶段分层）</div>
              <RobustTable results={results} />
            </div>
          </div>
        )}

        {tab === "cost" && (
          <div className="space-y-5">
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">交易成本敏感性（年化收益 vs 单边成本）</div>
              <CostChart results={results} />
            </div>
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">换手率统计</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(results.model_nav).map(([m, info]) => (
                  <div key={m} className="rounded-lg border border-ink-600/50 bg-ink-700/40 px-3 py-2">
                    <div className="text-xs text-slate-400">{m}</div>
                    <div className="font-mono text-sm mt-1">
                      年均换手 <span className="text-accent-glow">{fmtNum(info.turnover.annualized, 2)}</span>
                    </div>
                    <div className="font-mono text-xs text-slate-500">调仓次数 {info.turnover.n_rebalances ?? "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="px-6 py-3 border-t border-ink-700/60 text-xs text-slate-500">
        FactorLab 0.2.0 · 严格 expanding-window 样本外 · 财报 T+{ /* lag */ 90 }d 防泄漏 · 仅供研究，非投资建议
      </footer>
    </div>
  );
}
