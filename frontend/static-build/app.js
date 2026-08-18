/*
 * FactorLab · 构建无关（buildless）仪表盘
 * React 18 (UMD) + @babel/standalone + ECharts 5 (CDN)
 * 由 FastAPI 直接托管，无需 npm/vite 构建步骤。
 * 所有 API 走同源相对路径 /api/*。
 */
const { useState, useEffect, useRef, useMemo } = React;

const MODEL_COLORS = {
  eq_weight: "#3b82f6",
  elastic_net: "#22c55e",
  lightgbm: "#f59e0b",
  deep: "#a855f7",
  cross_section: "#06b6d4",
};

const fmtPct = (v) =>
  v === undefined || v === null || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(1)}%`;
const fmtNum = (v, d = 2) =>
  v === undefined || v === null || Number.isNaN(v) ? "—" : Number(v).toFixed(d);

const TAB_DEFS = [
  { key: "overview", label: "总览" },
  { key: "ic", label: "因子 IC" },
  { key: "groups", label: "分组收益" },
  { key: "robustness", label: "稳健性" },
  { key: "cost", label: "成本与换手" },
];

/* ---------- 通用 ECharts 容器 ---------- */
function EChart({ option, height = 360 }) {
  const ref = useRef(null);
  const inst = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    inst.current = echarts.init(ref.current, null, { renderer: "canvas" });
    const onResize = () => inst.current && inst.current.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      inst.current && inst.current.dispose();
    };
  }, []);
  useEffect(() => {
    if (inst.current && option) inst.current.setOption(option, true);
  }, [option]);
  return <div ref={ref} style={{ width: "100%", height }} />;
}

/* ---------- 小组件 ---------- */
function Stat({ label, value, sub }) {
  return (
    <div className="card px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="stat-value mt-1">{value}</div>
      {sub && <div className="text-xs text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function PerfTable({ results }) {
  const rows = Object.entries(results.model_nav || {}).map(([name, m]) => ({ name, perf: m.perf || {} }));
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
                <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: MODEL_COLORS[r.name] || "#888" }} />
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

function NavChart({ results }) {
  const series = Object.entries(results.model_nav || {}).map(([name, m]) => {
    const nav = m.nav || {};
    const dates = nav.dates || [];
    const values = nav.values || [];
    return {
      name,
      type: "line",
      showSymbol: false,
      smooth: true,
      lineStyle: { width: 2 },
      itemStyle: { color: MODEL_COLORS[name] || "#888" },
      data: dates.map((d, i) => [d, values[i]]),
    };
  });
  const option = {
    backgroundColor: "transparent",
    grid: { left: 60, right: 24, top: 44, bottom: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "time", axisLine: { lineStyle: { color: "#2a3650" } }, axisLabel: { color: "#7e93ad" } },
    yAxis: { type: "value", name: "净值", nameTextStyle: { color: "#7e93ad" }, splitLine: { lineStyle: { color: "#1a2233" } }, axisLabel: { color: "#7e93ad" } },
    series,
  };
  return <EChart option={option} height={380} />;
}

function IcHeatmap({ ic }) {
  const factors = Array.from(new Set((ic || []).map((r) => r.factor)));
  const methods = Array.from(new Set((ic || []).map((r) => r.method)));
  const data = (ic || []).map((r) => [methods.indexOf(r.method), factors.indexOf(r.factor), Number((r.ir || 0).toFixed(3))]);
  const option = {
    backgroundColor: "transparent",
    grid: { left: 90, right: 20, top: 24, bottom: 60 },
    tooltip: { position: "top", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    xAxis: { type: "category", data: methods, axisLabel: { color: "#9fb3cc" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "category", data: factors, axisLabel: { color: "#9fb3cc" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    visualMap: {
      min: -1, max: 1, calculable: true, orient: "horizontal", left: "center", bottom: 8,
      inRange: { color: ["#22c55e", "#0f1623", "#ef4444"] }, textStyle: { color: "#9fb3cc" },
    },
    series: [{ type: "heatmap", data, label: { show: true, color: "#e5edf7", fontSize: 10 }, emphasis: { itemStyle: { borderColor: "#fff", borderWidth: 1 } } }],
  };
  return <EChart option={option} height={460} />;
}

function DecayChart({ decay, factor }) {
  const rows = (decay && decay[factor]) || [];
  const option = {
    backgroundColor: "transparent",
    grid: { left: 56, right: 24, top: 36, bottom: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "category", data: rows.map((r) => r.lag), name: "lag(日)", axisLabel: { color: "#7e93ad" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "value", name: "RankIC", axisLabel: { color: "#7e93ad" }, splitLine: { lineStyle: { color: "#1a2233" } } },
    series: [
      { name: "IC均值", type: "line", smooth: true, data: rows.map((r) => r.ic_mean), itemStyle: { color: "#3b82f6" }, areaStyle: { color: "rgba(59,130,246,0.12)" } },
      { name: "IR", type: "line", smooth: true, data: rows.map((r) => r.ir), itemStyle: { color: "#f59e0b" } },
    ],
  };
  return rows.length ? <EChart option={option} height={320} /> : <Empty text="无衰减数据" />;
}

function GroupChart({ group }) {
  if (!group) return <Empty text="无分组数据" />;
  const groups = group.groups || {};
  const keys = Object.keys(groups);
  const series = keys.map((k) => ({
    name: k,
    type: "line",
    showSymbol: false,
    smooth: true,
    data: (groups[k].dates || []).map((d, i) => [d, (groups[k].values || [])[i]]),
    itemStyle: { color: k === keys[keys.length - 1] ? "#ef4444" : k === keys[0] ? "#22c55e" : undefined },
  }));
  const ls = group.long_short || {};
  series.push({
    name: "多空",
    type: "line",
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 3, type: "dashed" },
    data: (ls.dates || []).map((d, i) => [d, (ls.values || [])[i]]),
    itemStyle: { color: "#a855f7" },
  });
  const option = {
    backgroundColor: "transparent",
    grid: { left: 60, right: 24, top: 44, bottom: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "time", axisLabel: { color: "#7e93ad" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "value", name: "净值", axisLabel: { color: "#7e93ad" }, splitLine: { lineStyle: { color: "#1a2233" } } },
    series,
  };
  return <EChart option={option} height={360} />;
}

function RobustTable({ results }) {
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
            const r = results.robustness[m] || {};
            return (
              <tr key={m} className="border-t border-ink-600/40">
                <td className="px-4 py-2 font-medium">
                  <span className="inline-block w-2 h-2 rounded-full mr-2" style={{ background: MODEL_COLORS[m] || "#888" }} />
                  {m}
                </td>
                <td className="text-right px-4 py-2 font-mono text-bull">{fmtPct(r.bull && r.bull.annual_return)}</td>
                <td className="text-right px-4 py-2 font-mono">{fmtPct(r.neutral && r.neutral.annual_return)}</td>
                <td className="text-right px-4 py-2 font-mono text-bear">{fmtPct(r.bear && r.bear.annual_return)}</td>
                <td className="text-right px-4 py-2 font-mono">
                  {fmtNum(r.bull && r.bull.sharpe)} / {fmtNum(r.bear && r.bear.sharpe)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function CostChart({ results }) {
  const costScen = results.cost_scenarios || {};
  const costs = Object.keys(costScen);
  const models = Object.keys((costScen[costs[0]] || {}));
  const series = models.map((m) => ({
    name: m,
    type: "line",
    smooth: true,
    symbol: "circle",
    data: costs.map((c) => (costScen[c][m] ? costScen[c][m].annual_return : null)),
    itemStyle: { color: MODEL_COLORS[m] || "#888" },
  }));
  const option = {
    backgroundColor: "transparent",
    grid: { left: 60, right: 24, top: 44, bottom: 44 },
    tooltip: { trigger: "axis", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    legend: { textStyle: { color: "#9fb3cc" }, top: 0 },
    xAxis: { type: "category", data: costs.map((c) => `${c}bps`), name: "单边成本", axisLabel: { color: "#7e93ad" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "value", name: "年化收益", axisLabel: { color: "#7e93ad", formatter: (v) => `${(v * 100).toFixed(0)}%` }, splitLine: { lineStyle: { color: "#1a2233" } } },
    series,
  };
  return <EChart option={option} height={320} />;
}

function Empty({ text }) {
  return (
    <div className="flex items-center justify-center" style={{ height: 200, color: "#7e93ad" }}>
      {text || "暂无数据"}
    </div>
  );
}

/* ---------- 亮点组件 ---------- */
function KpiHero({ results }) {
  const nav = results.model_nav || {};
  const models = Object.keys(nav);
  let bestSharpe = null, bestRet = null;
  models.forEach((k) => {
    const p = nav[k].perf || {};
    if (!bestSharpe || (p.sharpe || -1e9) > (bestSharpe.p.sharpe || -1e9)) bestSharpe = { k, p };
    if (!bestRet || (p.annual_return || -1e9) > (bestRet.p.annual_return || -1e9)) bestRet = { k, p };
  });
  const ic = (results.ic_summary || []).slice().sort((a, b) => Math.abs(b.ir) - Math.abs(a.ir));
  const top = ic[0] || {};
  const MODEL_LABEL = { eq_weight: "等权复合", elastic_net: "ElasticNet", lightgbm: "LightGBM", deep: "深度学习" };
  const cards = [
    { label: "最佳夏普", name: MODEL_LABEL[bestSharpe && bestSharpe.k] || (bestSharpe && bestSharpe.k), val: fmtNum(bestSharpe && bestSharpe.p.sharpe, 2), sub: `年化 ${fmtPct(bestSharpe && bestSharpe.p.annual_return)}`, color: "#60a5fa" },
    { label: "最高年化", name: MODEL_LABEL[bestRet && bestRet.k] || (bestRet && bestRet.k), val: fmtPct(bestRet && bestRet.p.annual_return), sub: `Calmar ${fmtNum(bestRet && bestRet.p.calmar)}`, color: "#34d399" },
    { label: "Top 因子", name: top.factor, val: top.factor ? top.factor : "—", sub: `IC_IR ${fmtNum(top.ir, 3)} · |IC| ${fmtNum(top.abs_ic_mean, 3)}`, color: "#f59e0b" },
    { label: "最强回撤控制", name: bestSharpe && bestSharpe.k, val: fmtPct(bestSharpe && bestSharpe.p.max_drawdown), sub: `Calmar ${fmtNum(bestSharpe && bestSharpe.p.calmar)}`, color: "#f472b6" },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((c, i) => (
        <div key={i} className="card p-4 relative overflow-hidden">
          <div className="absolute top-0 left-0 h-1 w-full" style={{ background: c.color }} />
          <div className="text-xs uppercase tracking-wide text-slate-400">{c.label}</div>
          <div className="text-2xl font-bold mt-1" style={{ color: c.color }}>{c.val}</div>
          <div className="text-xs text-slate-500 mt-1">{c.name ? c.name : "—"}{c.sub ? ` · ${c.sub}` : ""}</div>
        </div>
      ))}
    </div>
  );
}

function IcLeaderboard({ ic }) {
  const rows = (ic || []).slice().sort((a, b) => Math.abs(b.ir) - Math.abs(a.ir));
  return (
    <div className="card overflow-hidden">
      <div className="text-sm text-slate-300 mb-2 font-medium">因子 IC 排行榜（按 |IC_IR| 排序）</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-slate-400 bg-ink-700/50">
            <tr>
              <th className="text-left px-3 py-2">#</th>
              <th className="text-left px-3 py-2">因子</th>
              <th className="text-right px-3 py-2">方法</th>
              <th className="text-right px-3 py-2">IC均值</th>
              <th className="text-right px-3 py-2">|IC|</th>
              <th className="text-right px-3 py-2">IC_IR</th>
              <th className="text-right px-3 py-2">IC&gt;0占比</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.factor + r.method} className="border-t border-ink-600/40" style={i === 0 ? { background: "rgba(245,158,11,0.08)" } : null}>
                <td className="px-3 py-1.5 text-slate-500">{i + 1}</td>
                <td className="px-3 py-1.5 font-medium">{r.factor}</td>
                <td className="text-right px-3 py-1.5 text-slate-400">{r.method}</td>
                <td className="text-right px-3 py-1.5 font-mono">{fmtNum(r.ic_mean, 3)}</td>
                <td className="text-right px-3 py-1.5 font-mono">{fmtNum(r.abs_ic_mean, 3)}</td>
                <td className="text-right px-3 py-1.5 font-mono" style={{ color: r.ir >= 0 ? "#ef4444" : "#22c55e" }}>{fmtNum(r.ir, 3)}</td>
                <td className="text-right px-3 py-1.5 font-mono">{fmtPct(r.ic_pos_ratio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DecayHeatmap({ decay }) {
  const factors = Object.keys(decay || {});
  if (!factors.length) return <Empty text="无衰减数据" />;
  const maxLag = Math.max(...factors.map((f) => (decay[f] || []).length));
  const data = [];
  let vmax = 0, vmin = 0;
  factors.forEach((f, fi) => {
    (decay[f] || []).forEach((p) => {
      const v = Number((p.ic || 0).toFixed(3));
      data.push([p.lag - 1, fi, v]);
      if (v > vmax) vmax = v;
      if (v < vmin) vmin = v;
    });
  });
  const option = {
    backgroundColor: "transparent",
    tooltip: { position: "top", backgroundColor: "#0f1623", borderColor: "#2a3650", textStyle: { color: "#e5edf7" } },
    grid: { left: 80, right: 20, top: 20, bottom: 60 },
    xAxis: { type: "category", data: Array.from({ length: maxLag }, (_, i) => i + 1), name: "滞后(日)", axisLabel: { color: "#9fb3cc" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    yAxis: { type: "category", data: factors, axisLabel: { color: "#9fb3cc" }, axisLine: { lineStyle: { color: "#2a3650" } } },
    visualMap: { min: vmin === 0 ? -0.01 : vmin, max: vmax === 0 ? 0.01 : vmax, calculable: true, orient: "horizontal", left: "center", bottom: 8, inRange: { color: ["#22c55e", "#0f1623", "#ef4444"] }, textStyle: { color: "#9fb3cc" } },
    series: [{ type: "heatmap", data, label: { show: false }, emphasis: { itemStyle: { borderColor: "#fff", borderWidth: 1 } } }],
  };
  return <EChart option={option} height={Math.max(260, factors.length * 34)} />;
}

/* ---------- 主应用 ---------- */
function App() {
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("overview");
  const [factor, setFactor] = useState("");
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState("");

  const load = () => {
    fetch("/api/results")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
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
      fetch("/api/run/state")
        .then((r) => r.json())
        .then((s) => {
          if (s.running && !running) setRunning(true);
          if (!s.running && running) {
            setRunning(false);
            load();
          }
        })
        .catch(() => {});
    }, 4000);
    return () => clearInterval(t);
    // eslint-disable-next-line
  }, []);

  const onRun = () => {
    setRunning(true);
    setRunMsg("流水线后台重算中…");
    const models = results && results.meta && results.meta.models ? results.meta.models.join(",") : "";
    const hpo = results && results.meta ? results.meta.hpo_trials || 0 : 0;
    fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ models, hpo }),
    })
      .then(() => {})
      .catch((e) => {
        setRunMsg("触发失败：" + String(e));
        setRunning(false);
      });
  };

  const meta = (results && results.meta) || {};
  const topFactors = useMemo(() => {
    if (!results) return [];
    return Array.from(new Set((results.ic_summary || []).map((r) => r.factor)));
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
      <div className="p-10 flex items-center justify-center" style={{ height: "100%" }}>
        <div className="text-accent-glow animate-pulse text-lg">加载中…</div>
      </div>
    );
  }

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-10 border-b border-ink-600/60" style={{ background: "rgba(10,14,23,0.8)", backdropFilter: "blur(8px)" }}>
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center font-bold text-white" style={{ background: "linear-gradient(135deg,#3b82f6,#a855f7)" }}>F</div>
            <div>
              <div className="text-lg font-semibold tracking-tight">FactorLab</div>
              <div className="text-xs text-slate-400">A股多因子研究 · 样本外回测 · 深度学习因子</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {running ? (
              <span className="pill text-accent-glow">● 重算中</span>
            ) : (
              <span className="pill" style={{ color: "#34d399", borderColor: "#22c55e" }}>● 就绪</span>
            )}
            <button
              onClick={onRun}
              disabled={running}
              className="rounded-lg px-3 py-1.5 text-sm font-medium transition disabled:opacity-40"
              style={{ background: "rgba(59,130,246,0.9)" }}
            >
              重新运行流水线
            </button>
          </div>
        </div>
        <nav className="px-6 flex gap-1 border-t border-ink-700/60">
          {TAB_DEFS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="px-4 py-2 text-sm border-b-2 transition"
              style={{
                color: tab === t.key ? "#60a5fa" : "#94a3b8",
                borderColor: tab === t.key ? "#3b82f6" : "transparent",
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="flex-1 px-6 py-5">
        <div className="flex flex-wrap gap-3 mb-5">
          <Stat label="样本区间" value={`${meta.start_date || "—"} ~ ${meta.end_date || "—"}`} />
          <Stat label="股票数" value={String(meta.universe_size ?? "—")} sub={`${meta.n_factors} 个因子`} />
          <Stat label="OOS 折数" value={String(meta.n_folds ?? "—")} sub={`持仓 ${meta.top_k} · 调仓 ${meta.rebal_freq}日`} />
          <Stat label="数据源" value={meta.data_source ?? "—"} sub={meta.deep_enabled ? "含深度学习模型" : ""} />
          <Stat label="生成时间" value={(meta.generated_at || "").replace("T", " ").slice(0, 16)} />
        </div>

        {tab === "overview" && (
          <div className="space-y-5">
            <KpiHero results={results} />
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">样本外净值曲线（基准=1.0）</div>
              <NavChart results={results} />
            </div>
            <PerfTable results={results} />
          </div>
        )}

        {tab === "ic" && (
          <div className="space-y-5">
            <IcLeaderboard ic={results.ic_summary} />
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">因子 IC / RankIC 信息比率（热力图）</div>
              <IcHeatmap ic={results.ic_summary} />
            </div>
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">因子收益衰减（RankIC 随持有期衰减）</div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs text-slate-400">因子：</span>
                <select value={factor} onChange={(e) => setFactor(e.target.value)} className="bg-ink-700 border border-ink-500 rounded px-2 py-1 text-sm" style={{ background: "#161f30" }}>
                  {topFactors.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <DecayChart decay={results.factor_decay} factor={factor} />
            </div>
            <div className="card p-4">
              <div className="text-sm text-slate-300 mb-2 font-medium">因子收益衰减热力图（IC × 滞后周期）</div>
              <DecayHeatmap decay={results.factor_decay} />
            </div>
          </div>
        )}

        {tab === "groups" && (
          <div className="space-y-5">
            <div className="card p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm text-slate-300 font-medium">分组净值（G1 最低 → G5 最高，虚线为多空）</div>
                <select value={factor} onChange={(e) => setFactor(e.target.value)} className="bg-ink-700 border border-ink-500 rounded px-2 py-1 text-sm" style={{ background: "#161f30" }}>
                  {topFactors.map((f) => (
                    <option key={f} value={f}>{f}</option>
                  ))}
                </select>
              </div>
              <GroupChart group={results.group_returns[factor]} />
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
                {Object.entries(results.model_nav || {}).map(([m, info]) => (
                  <div key={m} className="rounded-lg border border-ink-600/50 bg-ink-700/40 px-3 py-2">
                    <div className="text-xs text-slate-400">{m}</div>
                    <div className="font-mono text-sm mt-1">
                      年均换手 <span className="text-accent-glow">{fmtNum((info.turnover || {}).annualized, 2)}</span>
                    </div>
                    <div className="font-mono text-xs text-slate-500">调仓次数 {(info.turnover || {}).n_rebalances ?? "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="px-6 py-3 border-t border-ink-700/60 text-xs text-slate-500">
        FactorLab · 严格 expanding-window 样本外 · 财报 T+90d 防泄漏 · 仅供研究，非投资建议
        {runMsg ? <span className="ml-3 text-accent-glow">{runMsg}</span> : null}
      </footer>
    </div>
  );
}

ReactDOM.render(<App />, document.getElementById("root"));
