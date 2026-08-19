/*
 * FactorLab · 构建无关（buildless）专业仪表盘
 * React 18 (UMD) + @babel/standalone + ECharts 5 (CDN)
 * 设计目标：专业量化终端级（玻璃拟态 / 渐变面积图 / 统一暗色主题 / 精修排版）
 * 由 FastAPI 直接托管，无需 npm/vite 构建步骤。所有 API 走同源相对路径 /api/*。
 */
const { useState, useEffect, useRef, useMemo } = React;

const MODEL_COLORS = {
  eq_weight: "#38bdf8",
  elastic_net: "#34d399",
  lightgbm: "#f59e0b",
  deep: "#a78bfa",
  cross_section: "#22d3ee",
};
const C = {
  bull: "#f43f5e",
  bear: "#10b981",
  cyan: "#38bdf8",
  violet: "#a78bfa",
  amber: "#f59e0b",
  emerald: "#34d399",
  pink: "#f472b6",
  muted: "#64748b",
};

const fmtPct = (v) =>
  v === undefined || v === null || Number.isNaN(v) ? "—" : `${(v * 100).toFixed(1)}%`;
const fmtNum = (v, d = 2) =>
  v === undefined || v === null || Number.isNaN(v) ? "—" : Number(v).toFixed(d);

function hexA(hex, a) {
  const h = hex.replace("#", "");
  const r = parseInt(h.substring(0, 2), 16);
  const g = parseInt(h.substring(2, 4), 16);
  const b = parseInt(h.substring(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}
function gradArea(color, a0 = 0.32, a1 = 0) {
  return new echarts.graphic.LinearGradient(0, 0, 0, 1, [
    { offset: 0, color: hexA(color, a0) },
    { offset: 1, color: hexA(color, a1) },
  ]);
}

const TAB_DEFS = [
  { key: "overview", label: "总览" },
  { key: "ic", label: "因子 IC" },
  { key: "groups", label: "分组收益" },
  { key: "robustness", label: "稳健性" },
  { key: "cost", label: "成本与换手" },
];

/* ---------- 通用 ECharts 容器（统一 factorlab 主题） ---------- */
function EChart({ option, height = 360 }) {
  const ref = useRef(null);
  const inst = useRef(null);
  useEffect(() => {
    if (!ref.current) return;
    inst.current = echarts.init(ref.current, "factorlab", { renderer: "canvas" });
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

/* 迷你 sparkline（KPI 卡用） */
function Sparkline({ data, color, height = 44 }) {
  const option = {
    grid: { left: 0, right: 0, top: 4, bottom: 0 },
    xAxis: { type: "category", show: false, boundaryGap: false },
    yAxis: { type: "value", show: false, scale: true },
    tooltip: { show: false },
    series: [
      {
        type: "line",
        data,
        showSymbol: false,
        smooth: true,
        lineStyle: { width: 2, color },
        areaStyle: { color: gradArea(color, 0.28, 0) },
      },
    ],
  };
  return <EChart option={option} height={height} />;
}

/* ---------- 基础组件 ---------- */
function Stat({ label, value, sub, icon }) {
  return (
    <div className="glass card-hover px-4 py-3 fade-up">
      <div className="flex items-center justify-between">
        <div className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">{label}</div>
        {icon}
      </div>
      <div className="num text-lg font-semibold mt-1.5 text-slate-100">{value}</div>
      {sub && <div className="text-[11px] text-slate-500 mt-0.5">{sub}</div>}
    </div>
  );
}

function PerfTable({ results }) {
  const rows = Object.entries(results.model_nav || {}).map(([name, m]) => ({ name, perf: m.perf || {} }));
  return (
    <div className="glass overflow-hidden fade-up">
      <div className="px-4 pt-3.5 pb-2 text-sm font-semibold text-slate-200">模型样本外业绩</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-400 text-[12px] uppercase tracking-wide">
              <th className="text-left px-4 py-2.5 font-medium">模型</th>
              <th className="text-right px-4 py-2.5 font-medium">年化收益</th>
              <th className="text-right px-4 py-2.5 font-medium">年化波动</th>
              <th className="text-right px-4 py-2.5 font-medium">Sharpe</th>
              <th className="text-right px-4 py-2.5 font-medium">最大回撤</th>
              <th className="text-right px-4 py-2.5 font-medium">Calmar</th>
              <th className="text-right px-4 py-2.5 font-medium">累计收益</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.name} className="border-t border-white/5 hover:bg-white/[0.03] transition">
                <td className="px-4 py-2.5 font-medium text-slate-100">
                  <span className="inline-block w-2 h-2 rounded-full mr-2.5 align-middle" style={{ background: MODEL_COLORS[r.name] || "#888", boxShadow: `0 0 8px ${MODEL_COLORS[r.name] || "#888"}` }} />
                  {r.name}
                </td>
                <td className="text-right px-4 py-2.5 num text-bull">{fmtPct(r.perf.annual_return)}</td>
                <td className="text-right px-4 py-2.5 num text-slate-300">{fmtPct(r.perf.annual_vol)}</td>
                <td className="text-right px-4 py-2.5 num font-semibold text-cyan">{fmtNum(r.perf.sharpe)}</td>
                <td className="text-right px-4 py-2.5 num text-bear">{fmtPct(r.perf.max_drawdown)}</td>
                <td className="text-right px-4 py-2.5 num text-slate-300">{fmtNum(r.perf.calmar)}</td>
                <td className="text-right px-4 py-2.5 num text-bull">{fmtPct(r.perf.total_return)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NavChart({ results }) {
  const series = Object.entries(results.model_nav || {}).map(([name, m]) => {
    const nav = m.nav || {};
    const dates = nav.dates || [];
    const values = nav.values || [];
    const color = MODEL_COLORS[name] || "#888";
    const isBest = name === Object.keys(results.model_nav)[0];
    return {
      name,
      type: "line",
      showSymbol: false,
      smooth: true,
      lineStyle: { width: isBest ? 2.6 : 1.8, color, shadowColor: color, shadowBlur: isBest ? 14 : 6 },
      itemStyle: { color },
      emphasis: { focus: "series" },
      data: dates.map((d, i) => [d, values[i]]),
    };
  });
  const option = {
    grid: { left: 64, right: 24, top: 30, bottom: 36 },
    legend: { top: 0, itemWidth: 14, itemHeight: 8, textStyle: { color: "#94a3b8" } },
    tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: "#334155" } } },
    xAxis: { type: "time" },
    yAxis: { type: "value", name: "净值", nameTextStyle: { color: "#64748b", align: "left" }, scale: true },
    series: [
      ...series,
      {
        type: "line",
        data: [],
        markLine: {
          silent: true,
          symbol: "none",
          lineStyle: { color: "#475569", type: "dashed", width: 1 },
          data: [{ yAxis: 1 }],
          label: { show: false },
        },
      },
    ],
  };
  return <EChart option={option} height={380} />;
}

function IcHeatmap({ ic }) {
  const factors = Array.from(new Set((ic || []).map((r) => r.factor)));
  const methods = Array.from(new Set((ic || []).map((r) => r.method)));
  const data = (ic || []).map((r) => [methods.indexOf(r.method), factors.indexOf(r.factor), Number((r.ir || 0).toFixed(3))]);
  const option = {
    grid: { left: 96, right: 24, top: 28, bottom: 56 },
    tooltip: {
      position: "top",
      formatter: (p) => `${factors[p.value[1]]} · ${methods[p.value[0]]}<br/>IR: <b>${p.value[2]}</b>`,
    },
    xAxis: { type: "category", data: methods, axisLabel: { color: "#9fb3cc" } },
    yAxis: { type: "category", data: factors, axisLabel: { color: "#9fb3cc" } },
    visualMap: {
      min: -0.6, max: 0.6, calculable: true, orient: "horizontal", left: "center", bottom: 6,
      itemWidth: 14, itemHeight: 180,
      inRange: { color: ["#1d4ed8", "#0b1220", "#f43f5e"] },
      textStyle: { color: "#9fb3cc" },
    },
    series: [{ type: "heatmap", data, itemStyle: { borderColor: "#0a0f1c", borderWidth: 2, borderRadius: 4 }, label: { show: true, color: "#e5edf7", fontSize: 10 }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(255,255,255,0.4)" } } }],
  };
  return <EChart option={option} height={460} />;
}

function DecayChart({ decay, factor }) {
  const rows = (decay && decay[factor]) || [];
  if (!rows.length) return <Empty text="无衰减数据" />;
  const option = {
    grid: { left: 56, right: 24, top: 30, bottom: 40 },
    legend: { top: 0, textStyle: { color: "#94a3b8" } },
    tooltip: { trigger: "axis" },
    xAxis: { type: "category", data: rows.map((r) => r.lag), name: "lag(日)" },
    yAxis: { type: "value", name: "RankIC" },
    series: [
      {
        name: "IC均值", type: "line", smooth: true, symbol: "circle", symbolSize: 7,
        data: rows.map((r) => r.ic_mean), itemStyle: { color: C.cyan },
        lineStyle: { width: 2.6, color: C.cyan, shadowColor: C.cyan, shadowBlur: 12 },
        areaStyle: { color: gradArea(C.cyan, 0.28, 0) },
      },
      { name: "IR", type: "line", smooth: true, symbol: "circle", symbolSize: 6, data: rows.map((r) => r.ir), itemStyle: { color: C.amber }, lineStyle: { width: 2, color: C.amber } },
    ],
  };
  return <EChart option={option} height={320} />;
}

function GroupChart({ group }) {
  if (!group) return <Empty text="无分组数据" />;
  const groups = group.groups || {};
  const keys = Object.keys(groups);
  const palette = ["#10b981", "#22d3ee", "#64748b", "#a78bfa", "#f43f5e"];
  const series = keys.map((k, i) => ({
    name: k,
    type: "line",
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 2, color: palette[i % palette.length] },
    itemStyle: { color: palette[i % palette.length] },
    data: (groups[k].dates || []).map((d, j) => [d, (groups[k].values || [])[j]]),
  }));
  const ls = group.long_short || {};
  series.push({
    name: "多空",
    type: "line",
    showSymbol: false,
    smooth: true,
    lineStyle: { width: 3, color: C.violet, shadowColor: C.violet, shadowBlur: 14 },
    itemStyle: { color: C.violet },
    areaStyle: { color: gradArea(C.violet, 0.16, 0) },
    z: 5,
    data: (ls.dates || []).map((d, i) => [d, (ls.values || [])[i]]),
  });
  const option = {
    grid: { left: 64, right: 24, top: 30, bottom: 36 },
    legend: { top: 0, textStyle: { color: "#94a3b8" } },
    tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: "#334155" } } },
    xAxis: { type: "time" },
    yAxis: { type: "value", name: "净值", scale: true },
    series,
  };
  return <EChart option={option} height={360} />;
}

function RobustTable({ results }) {
  const models = Object.keys(results.robustness || {});
  const cell = (v, key) =>
    v && v[key] !== undefined ? (
      <span className="num">{fmtPct(v[key])}</span>
    ) : (
      <span className="text-slate-600">—</span>
    );
  return (
    <div className="glass overflow-hidden fade-up">
      <div className="px-4 pt-3.5 pb-2 text-sm font-semibold text-slate-200">牛 / 震荡 / 熊 市分阶段表现</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-400 text-[12px] uppercase tracking-wide">
              <th className="text-left px-4 py-2.5 font-medium">模型</th>
              <th className="text-right px-4 py-2.5 font-medium text-bull">牛市 年化</th>
              <th className="text-right px-4 py-2.5 font-medium">震荡 年化</th>
              <th className="text-right px-4 py-2.5 font-medium text-bear">熊市 年化</th>
              <th className="text-right px-4 py-2.5 font-medium text-cyan">牛/熊 Sharpe</th>
            </tr>
          </thead>
          <tbody>
            {models.map((m) => {
              const r = results.robustness[m] || {};
              return (
                <tr key={m} className="border-t border-white/5 hover:bg-white/[0.03] transition">
                  <td className="px-4 py-2.5 font-medium text-slate-100">
                    <span className="inline-block w-2 h-2 rounded-full mr-2.5 align-middle" style={{ background: MODEL_COLORS[m] || "#888", boxShadow: `0 0 8px ${MODEL_COLORS[m] || "#888"}` }} />
                    {m}
                  </td>
                  <td className="text-right px-4 py-2.5">{cell(r.bull, "annual_return")}</td>
                  <td className="text-right px-4 py-2.5">{cell(r.neutral, "annual_return")}</td>
                  <td className="text-right px-4 py-2.5">{cell(r.bear, "annual_return")}</td>
                  <td className="text-right px-4 py-2.5 num text-slate-300">
                    {r.bull ? fmtNum(r.bull.sharpe) : "—"} / {r.bear ? fmtNum(r.bear.sharpe) : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CostChart({ results }) {
  const costScen = results.cost_scenarios || {};
  const costs = Object.keys(costScen);
  const models = Object.keys(costScen[costs[0]] || {});
  const series = models.map((m) => {
    const color = MODEL_COLORS[m] || "#888";
    return {
      name: m,
      type: "line",
      smooth: true,
      symbol: "circle",
      symbolSize: 7,
      data: costs.map((c) => (costScen[c][m] ? costScen[c][m].annual_return : null)),
      itemStyle: { color },
      lineStyle: { width: 2.4, color, shadowColor: color, shadowBlur: 10 },
    };
  });
  const option = {
    grid: { left: 64, right: 24, top: 30, bottom: 40 },
    legend: { top: 0, textStyle: { color: "#94a3b8" } },
    tooltip: { trigger: "axis", valueFormatter: (v) => (v == null ? "—" : fmtPct(v)) },
    xAxis: { type: "category", data: costs.map((c) => `${c}bps`), name: "单边成本" },
    yAxis: { type: "value", name: "年化收益", axisLabel: { formatter: (v) => `${(v * 100).toFixed(0)}%` } },
    series,
  };
  return <EChart option={option} height={320} />;
}

function Empty({ text }) {
  return (
    <div className="flex items-center justify-center" style={{ height: 200, color: "#64748b" }}>
      <div className="text-center">
        <div style={{ fontSize: 28, opacity: 0.4 }}>∅</div>
        <div className="mt-2 text-sm">{text || "暂无数据"}</div>
      </div>
    </div>
  );
}

function Skeleton() {
  return (
    <div className="p-6 space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[0, 1, 2, 3].map((i) => (<div key={i} className="skeleton h-24" />))}
      </div>
      <div className="skeleton h-80" />
      <div className="skeleton h-64" />
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
  const sparkFor = (k) => {
    const v = (nav[k] && nav[k].nav && nav[k].nav.values) || [];
    const s = v.length > 40 ? v.filter((_, i) => i % Math.ceil(v.length / 40) === 0) : v;
    return s;
  };
  const cards = [
    { label: "最佳夏普", name: MODEL_LABEL[bestSharpe && bestSharpe.k] || (bestSharpe && bestSharpe.k), val: fmtNum(bestSharpe && bestSharpe.p.sharpe, 2), sub: `年化 ${fmtPct(bestSharpe && bestSharpe.p.annual_return)}`, color: C.cyan, spark: bestSharpe && sparkFor(bestSharpe.k), colorK: bestSharpe && bestSharpe.k },
    { label: "最高年化", name: MODEL_LABEL[bestRet && bestRet.k] || (bestRet && bestRet.k), val: fmtPct(bestRet && bestRet.p.annual_return), sub: `Calmar ${fmtNum(bestRet && bestRet.p.calmar)}`, color: C.emerald, spark: bestRet && sparkFor(bestRet.k), colorK: bestRet && bestRet.k },
    { label: "Top 因子", name: top.factor, val: top.factor ? top.factor : "—", sub: `IC_IR ${fmtNum(top.ir, 3)} · |IC| ${fmtNum(top.abs_ic_mean, 3)}`, color: C.amber, spark: null },
    { label: "回撤控制", name: bestSharpe && bestSharpe.k, val: fmtPct(bestSharpe && bestSharpe.p.max_drawdown), sub: `Calmar ${fmtNum(bestSharpe && bestSharpe.p.calmar)}`, color: C.pink, spark: null },
  ];
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
      {cards.map((c, i) => (
        <div key={i} className="glass card-hover relative overflow-hidden p-4 fade-up" style={{ animationDelay: `${i * 60}ms` }}>
          <div className="absolute top-0 left-0 h-[3px] w-full" style={{ background: `linear-gradient(90deg, ${c.color}, transparent)` }} />
          <div className="flex items-start justify-between">
            <div className="text-[11px] uppercase tracking-wider text-slate-400 font-medium">{c.label}</div>
            <div className="w-2 h-2 rounded-full" style={{ background: c.color, boxShadow: `0 0 10px ${c.color}` }} />
          </div>
          <div className="num text-[26px] font-bold mt-2 leading-none" style={{ color: c.color }}>{c.val}</div>
          <div className="text-[11px] text-slate-400 mt-1.5 truncate">{c.name ? c.name : "—"}{c.sub ? ` · ${c.sub}` : ""}</div>
          {c.spark && c.spark.length > 1 && (
            <div className="mt-1.5 -mb-1">
              <Sparkline data={c.spark} color={MODEL_COLORS[c.colorK] || c.color} height={34} />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function IcLeaderboard({ ic }) {
  const rows = (ic || []).slice().sort((a, b) => Math.abs(b.ir) - Math.abs(a.ir));
  const maxIr = Math.max(0.0001, ...rows.map((r) => Math.abs(r.ir)));
  return (
    <div className="glass overflow-hidden fade-up">
      <div className="px-4 pt-3.5 pb-2 text-sm font-semibold text-slate-200">因子 IC 排行榜（按 |IC_IR| 排序）</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-slate-400 text-[12px] uppercase tracking-wide">
              <th className="text-left px-3 py-2.5 font-medium w-10">#</th>
              <th className="text-left px-3 py-2.5 font-medium">因子</th>
              <th className="text-right px-3 py-2.5 font-medium">方法</th>
              <th className="text-right px-3 py-2.5 font-medium">IC均值</th>
              <th className="text-right px-3 py-2.5 font-medium">|IC|</th>
              <th className="text-left px-3 py-2.5 font-medium">IC_IR</th>
              <th className="text-right px-3 py-2.5 font-medium">IC&gt;0占比</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={r.factor + r.method} className="border-t border-white/5 hover:bg-white/[0.03] transition" style={i === 0 ? { background: "rgba(245,158,11,0.06)" } : null}>
                <td className="px-3 py-2 text-slate-500">
                  <span className={"inline-flex items-center justify-center w-5 h-5 rounded-md text-[11px] font-bold " + (i === 0 ? "text-amber" : "text-slate-400")} style={i === 0 ? { background: "rgba(245,158,11,0.16)" } : { background: "rgba(148,163,184,0.08)" }}>{i + 1}</span>
                </td>
                <td className="px-3 py-2 font-medium text-slate-100">{r.factor}</td>
                <td className="text-right px-3 py-2 text-slate-400">{r.method}</td>
                <td className="text-right px-3 py-2 num text-slate-300">{fmtNum(r.ic_mean, 3)}</td>
                <td className="text-right px-3 py-2 num text-slate-300">{fmtNum(r.abs_ic_mean, 3)}</td>
                <td className="px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className="num font-semibold" style={{ color: r.ir >= 0 ? C.bull : C.bear }}>{fmtNum(r.ir, 3)}</span>
                    <div className="w-16 h-1.5 rounded-full bg-white/5 overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${Math.min(100, (Math.abs(r.ir) / maxIr) * 100)}%`, background: r.ir >= 0 ? C.bull : C.bear }} />
                    </div>
                  </div>
                </td>
                <td className="text-right px-3 py-2 num text-slate-400">{fmtPct(r.ic_pos_ratio)}</td>
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
  let vmax = -1e9, vmin = 1e9;
  factors.forEach((f, fi) => {
    (decay[f] || []).forEach((p) => {
      const v = Number((p.ic || 0).toFixed(3));
      data.push([p.lag - 1, fi, v]);
      if (v > vmax) vmax = v;
      if (v < vmin) vmin = v;
    });
  });
  const option = {
    tooltip: { position: "top", formatter: (p) => `${factors[p.value[1]]} · lag ${p.value[0] + 1}<br/>RankIC: <b>${p.value[2]}</b>` },
    grid: { left: 80, right: 24, top: 16, bottom: 48 },
    xAxis: { type: "category", data: Array.from({ length: maxLag }, (_, i) => i + 1), name: "滞后(日)" },
    yAxis: { type: "category", data: factors },
    visualMap: { min: vmin, max: vmax, calculable: true, orient: "horizontal", left: "center", bottom: 2, itemWidth: 12, itemHeight: 160, inRange: { color: ["#1d4ed8", "#0b1220", "#f43f5e"] }, textStyle: { color: "#9fb3cc" } },
    series: [{ type: "heatmap", data, itemStyle: { borderColor: "#0a0f1c", borderWidth: 2, borderRadius: 4 }, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(255,255,255,0.4)" } } }],
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
        <div className="glass p-8 text-center max-w-lg mx-auto">
          <div className="text-bull text-lg font-semibold">无法加载结果数据</div>
          <div className="text-slate-400 mt-2 text-sm">{error}</div>
          <div className="text-slate-500 mt-4 text-sm">
            请先运行 <code className="pill">factorlab run</code> 生成 outputs/results/results.json，
            或启动 <code className="pill">factorlab serve</code>。
          </div>
        </div>
      </div>
    );
  }

  if (!results) return <Skeleton />;

  const Logo = () => (
    <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: "linear-gradient(135deg,#38bdf8,#6366f1)", boxShadow: "0 8px 22px -6px rgba(99,102,241,0.6)" }}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="3,16 9,10 13,13 21,5" />
        <polyline points="15,5 21,5 21,11" />
      </svg>
    </div>
  );

  return (
    <div className="min-h-full flex flex-col">
      <header className="sticky top-0 z-20" style={{ background: "rgba(8,13,24,0.72)", backdropFilter: "blur(14px)", borderBottom: "1px solid rgba(148,163,184,0.1)" }}>
        <div className="px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Logo />
            <div>
              <div className="text-lg font-bold tracking-tight text-slate-50">Factor<span className="grad-text">Lab</span></div>
              <div className="text-[11px] text-slate-400 -mt-0.5">A股多因子研究 · 样本外回测 · 深度学习因子</div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {running ? (
              <span className="pill" style={{ color: C.cyan, borderColor: "rgba(56,189,248,0.4)" }}>
                <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: C.cyan }} /> 重算中
              </span>
            ) : (
              <span className="pill" style={{ color: C.emerald, borderColor: "rgba(16,185,129,0.4)" }}>
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: C.emerald }} /> 就绪
              </span>
            )}
            <button onClick={onRun} disabled={running} className="btn-primary px-3.5 py-1.5 text-sm disabled:opacity-40 disabled:cursor-not-allowed">
              {running ? "运行中…" : "重新运行流水线"}
            </button>
          </div>
        </div>
        <div className="px-6 pb-0">
          <div className="seg">
            {TAB_DEFS.map((t) => (
              <button key={t.key} className={tab === t.key ? "active" : ""} onClick={() => setTab(t.key)}>
                {t.label}
              </button>
            ))}
          </div>
        </div>
        <div className="h-3" />
      </header>

      <main className="flex-1 px-6 py-5 max-w-[1400px] w-full mx-auto">
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
            <div className="glass p-4 fade-up">
              <div className="flex items-center justify-between mb-1">
                <div className="text-sm font-semibold text-slate-200">样本外净值曲线</div>
                <div className="text-[11px] text-slate-500">基准 = 1.0 · 扩张窗口 · 隔日换仓</div>
              </div>
              <NavChart results={results} />
            </div>
            <PerfTable results={results} />
          </div>
        )}

        {tab === "ic" && (
          <div className="space-y-5">
            <IcLeaderboard ic={results.ic_summary} />
            <div className="glass p-4 fade-up">
              <div className="text-sm font-semibold text-slate-200 mb-1">因子 IC / RankIC 信息比率（热力图）</div>
              <IcHeatmap ic={results.ic_summary} />
            </div>
            <div className="glass p-4 fade-up">
              <div className="text-sm font-semibold text-slate-200 mb-2">因子收益衰减</div>
              <div className="flex items-center gap-3 mb-3">
                <span className="text-xs text-slate-400">因子：</span>
                <select value={factor} onChange={(e) => setFactor(e.target.value)} className="rounded-lg border border-white/10 px-2.5 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan/50" style={{ background: "#0e1424" }}>
                  {topFactors.map((f) => (<option key={f} value={f}>{f}</option>))}
                </select>
              </div>
              <DecayChart decay={results.factor_decay} factor={factor} />
            </div>
            <div className="glass p-4 fade-up">
              <div className="text-sm font-semibold text-slate-200 mb-1">因子收益衰减热力图（RankIC × 滞后周期）</div>
              <DecayHeatmap decay={results.factor_decay} />
            </div>
          </div>
        )}

        {tab === "groups" && (
          <div className="space-y-5">
            <div className="glass p-4 fade-up">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-semibold text-slate-200">分组净值（G1 最低 → G5 最高，虚线为多空）</div>
                <select value={factor} onChange={(e) => setFactor(e.target.value)} className="rounded-lg border border-white/10 px-2.5 py-1.5 text-sm text-slate-200 outline-none focus:border-cyan/50" style={{ background: "#0e1424" }}>
                  {topFactors.map((f) => (<option key={f} value={f}>{f}</option>))}
                </select>
              </div>
              <GroupChart group={results.group_returns[factor]} />
              {results.group_returns[factor] && (
                <div className="text-xs text-slate-400 mt-3 flex gap-4 flex-wrap">
                  <span>多空年化 <b className="num text-bull">{fmtPct(results.group_returns[factor].ls_stats.annual_return)}</b></span>
                  <span>多空 Sharpe <b className="num text-cyan">{fmtNum(results.group_returns[factor].ls_stats.sharpe)}</b></span>
                  <span>多空最大回撤 <b className="num text-bear">{fmtPct(results.group_returns[factor].ls_stats.max_drawdown)}</b></span>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "robustness" && (
          <div className="space-y-5">
            <RobustTable results={results} />
          </div>
        )}

        {tab === "cost" && (
          <div className="space-y-5">
            <div className="glass p-4 fade-up">
              <div className="text-sm font-semibold text-slate-200 mb-1">交易成本敏感性（年化收益 vs 单边成本）</div>
              <CostChart results={results} />
            </div>
            <div className="glass p-4 fade-up">
              <div className="text-sm font-semibold text-slate-200 mb-3">换手率统计</div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(results.model_nav || {}).map(([m, info]) => (
                  <div key={m} className="rounded-xl border border-white/5 bg-white/[0.02] px-3 py-2.5 card-hover">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <span className="w-2 h-2 rounded-full" style={{ background: MODEL_COLORS[m] || "#888" }} />{m}
                    </div>
                    <div className="num text-sm mt-1.5 text-slate-100">
                      年均换手 <span className="text-cyan font-semibold">{fmtNum((info.turnover || {}).annualized, 2)}</span>
                    </div>
                    <div className="num text-[11px] text-slate-500 mt-0.5">调仓次数 {(info.turnover || {}).n_rebalances ?? "—"}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="px-6 py-4 text-[11px] text-slate-500 border-t border-white/5 mt-2">
        FactorLab · 严格 expanding-window 样本外 · 财报 T+90d 防泄漏 · 仅供研究，非投资建议
        {runMsg ? <span className="ml-3 text-cyan">{runMsg}</span> : null}
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
