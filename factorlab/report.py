"""生成自包含的量化研究报告（HTML + ECharts CDN，内联数据，可双击打开）。

读取 pipeline 产出的 results.json，渲染 KPI 卡片、模型净值对比、因子 IC 排行榜、
因子收益衰减热力图、分组多空净值、交易成本稳健性、牛熊稳健性等图表。
设计语言与实时仪表盘（frontend/static-build）保持一致：玻璃拟态 + 渐变面积 + 统一暗色主题。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .config import Settings
from .utils.common import PROJECT_ROOT


def _fmt_pct(x: float, nd: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.{nd}f}%"


def _fmt_num(x: float, nd: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{nd}f}"


def build_report(results: dict[str, Any], out_path: str | Path) -> Path:
    """根据 results 字典生成报告 HTML，写入 out_path，返回路径。"""
    out_path = Path(out_path)
    data_json = json.dumps(results, ensure_ascii=False)

    html = _TEMPLATE.replace("__DATA__", data_json).replace("__ECHARTS_THEME__", _ECHARTS_THEME)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def build_report_from_config(config: Settings | None = None, out_path: str | Path | None = None) -> Path:
    """便捷入口：从 results.json 生成报告。"""
    config = config or Settings.load()
    results_path = (PROJECT_ROOT / config.output.result_dir) / "results.json"
    if not results_path.exists():
        results_path = PROJECT_ROOT / "outputs" / "results" / "results.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    out_path = Path(out_path) if out_path else ((PROJECT_ROOT / config.output.result_dir) / "report.html")
    return build_report(results, out_path)


# 与仪表盘一致的 ECharts 暗色主题（在报告内独立注册，保证自包含）
_ECHARTS_THEME = """
(function(){ if(!window.echarts) return;
  echarts.registerTheme('factorlab', {
    color:['#38bdf8','#34d399','#f59e0b','#a78bfa','#f472b6','#22d3ee','#fb7185'],
    backgroundColor:'transparent',
    textStyle:{color:'#cbd5e1',fontFamily:'Inter, -apple-system, sans-serif'},
    title:{textStyle:{color:'#e2e8f0',fontWeight:600}},
    legend:{textStyle:{color:'#94a3b8',fontSize:12},inactiveColor:'#475569'},
    categoryAxis:{axisLine:{lineStyle:{color:'#2a3650'}},axisTick:{show:false},axisLabel:{color:'#64748b',fontSize:11},splitLine:{show:false,lineStyle:{color:'rgba(148,163,184,0.06)'}}},
    valueAxis:{axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#64748b',fontSize:11},splitLine:{lineStyle:{color:'rgba(148,163,184,0.08)'}}},
    timeAxis:{axisLine:{lineStyle:{color:'#2a3650'}},axisLabel:{color:'#64748b',fontSize:11},splitLine:{show:false}},
    tooltip:{backgroundColor:'rgba(10,15,28,0.94)',borderColor:'#2a3650',borderWidth:1,textStyle:{color:'#e2e8f0',fontSize:12},extraCssText:'border-radius:12px;box-shadow:0 16px 48px rgba(0,0,0,0.55);backdrop-filter:blur(10px);padding:10px 14px;'}
  });
})();
"""

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>FactorLab · 多因子研究报告</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin/>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap" rel="stylesheet"/>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.1/dist/echarts.min.js"></script>
<style>
  :root{
    --bg:#070b14; --panel:rgba(20,28,48,0.72); --panel2:rgba(12,18,32,0.62);
    --line:rgba(148,163,184,0.12); --txt:#e5edf7; --muted:#8b98a9;
    --cyan:#38bdf8; --violet:#a78bfa; --bull:#f43f5e; --bear:#10b981; --amber:#f59e0b;
  }
  *{box-sizing:border-box}
  html,body{margin:0;}
  body{
    background:
      radial-gradient(1100px 700px at 12% -8%, rgba(56,189,248,0.12), transparent 60%),
      radial-gradient(900px 600px at 92% 4%, rgba(167,139,250,0.12), transparent 55%),
      linear-gradient(180deg,#080d18 0%, #060912 100%);
    background-attachment:fixed;
    color:var(--txt);
    font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;
  }
  .num{font-family:'JetBrains Mono',ui-monospace,monospace;font-variant-numeric:tabular-nums;letter-spacing:-.02em;}
  .wrap{max-width:1200px;margin:0 auto;padding:36px 22px 64px;}
  header.head{display:flex;flex-direction:column;gap:14px;padding-bottom:22px;margin-bottom:8px;border-bottom:1px solid var(--line);}
  .logo{display:flex;align-items:center;gap:12px;}
  .logo .mark{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#38bdf8,#6366f1);box-shadow:0 8px 22px -6px rgba(99,102,241,0.6);}
  header.head h1{margin:0;font-size:26px;font-weight:800;letter-spacing:.3px;}
  header.head h1 span{background:linear-gradient(135deg,#38bdf8,#a78bfa);-webkit-background-clip:text;background-clip:text;color:transparent;}
  .sub{color:var(--muted);font-size:13px;line-height:1.7;}
  .badge{display:inline-block;background:rgba(12,18,32,0.6);border:1px solid var(--line);color:var(--cyan);border-radius:999px;padding:3px 11px;font-size:12px;margin:0 8px 8px 0;}
  h2.sec{font-size:17px;font-weight:700;margin:34px 0 14px;padding-left:12px;border-left:3px solid var(--cyan);color:#eef4fb;}
  .glass{border-radius:16px;border:1px solid var(--line);background:linear-gradient(180deg,var(--panel),var(--panel2));backdrop-filter:blur(14px);box-shadow:0 1px 0 0 rgba(255,255,255,0.04) inset,0 20px 50px -18px rgba(2,6,23,0.7);}
  .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;}
  .kpi{position:relative;overflow:hidden;padding:18px 18px 16px;}
  .kpi .accent{position:absolute;top:0;left:0;height:3px;width:100%;background:linear-gradient(90deg,var(--cyan),transparent);}
  .kpi .label{color:var(--muted);font-size:12px;margin-bottom:10px;}
  .kpi .val{font-size:26px;font-weight:800;}
  .kpi .meta{color:var(--muted);font-size:12px;margin-top:8px;}
  .card{padding:18px;margin-top:14px;}
  .chart{width:100%;height:360px;}
  .chart.tall{height:430px;}
  table{width:100%;border-collapse:collapse;font-size:13px;margin-top:6px;}
  th,td{padding:9px 12px;border-bottom:1px solid var(--line);text-align:right;}
  th:first-child,td:first-child{text-align:left;}
  thead th{color:var(--muted);font-weight:600;}
  tbody tr:hover{background:rgba(255,255,255,0.03);}
  .pos{color:var(--bull);} .neg{color:var(--bear);}
  .note{color:var(--muted);font-size:12px;margin-top:10px;line-height:1.6;}
  footer{margin-top:48px;border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:12px;line-height:1.8;}
  @media(max-width:860px){.kpis{grid-template-columns:repeat(2,1fr)}}
</style>
</head>
<body>
<div class="wrap">
  <header class="head">
    <div class="logo">
      <div class="mark"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><polyline points="3,16 9,10 13,13 21,5"/><polyline points="15,5 21,5 21,11"/></svg></div>
      <h1>Factor<span>Lab</span> · 多因子研究报告</h1>
    </div>
    <div class="sub" id="meta"></div>
  </header>

  <h2 class="sec">核心指标概览</h2>
  <div class="kpis" id="kpis"></div>

  <h2 class="sec">模型样本外净值对比</h2>
  <div class="glass card"><div id="navChart" class="chart tall"></div>
    <div class="note">净值基于样本外（OOS）扩张窗口训练，因子打分隔日换仓，已扣除双边交易成本。</div>
  </div>

  <h2 class="sec">因子 IC 排行榜</h2>
  <div class="glass card">
    <table id="icTable"><thead><tr>
      <th>因子</th><th>方法</th><th>IC 均值</th><th>|IC|</th><th>IC_IR</th><th>IC&gt;0 占比</th>
    </tr></thead><tbody></tbody></table>
    <div class="note">IC_IR = IC均值 / IC标准差，衡量因子选股能力的稳定性与信息比率；|IC| 越高、IR 越大越好。</div>
  </div>

  <h2 class="sec">因子收益衰减热力图（IC × 滞后周期）</h2>
  <div class="glass card"><div id="decayChart" class="chart tall"></div>
    <div class="note">横轴为收益滞后天数，纵轴为因子；颜色越红代表正向预测力越强、越蓝越弱。衰减越慢的因子越具交易价值。</div>
  </div>

  <h2 class="sec">分组多空净值（Top 因子）</h2>
  <div class="glass card"><div id="groupChart" class="chart tall"></div>
    <div class="note" id="groupNote"></div>
  </div>

  <h2 class="sec">交易成本敏感度</h2>
  <div class="glass card"><div id="costChart" class="chart"></div>
    <div class="note">横轴为双边交易成本（bps），展示各模型年化收益随成本上升的衰减，用于评估策略在真实摩擦下的鲁棒性。</div>
  </div>

  <h2 class="sec">牛 / 震荡 / 熊 市稳健性</h2>
  <div class="glass card"><div id="robChart" class="chart"></div>
    <div class="note">按市场状态切分样本，比较各模型在不同市况下的年化收益，检验策略是否过度依赖单一行情。</div>
  </div>

  <footer id="footer"></footer>
</div>

<script>
__ECHARTS_THEME__
const DATA = __DATA__;
const C = {bg:'#070b14',line:'rgba(148,163,184,0.12)',txt:'#e5edf7',muted:'#8b98a9',
  cyan:'#38bdf8',violet:'#a78bfa',bull:'#f43f5e',bear:'#10b981',amber:'#f59e0b',gold:'#f59e0b'};
const MODEL_COLORS = {eq_weight:'#38bdf8',elastic_net:'#34d399',lightgbm:'#f59e0b',deep:'#a78bfa'};
const MODEL_LABEL = {eq_weight:'等权复合',elastic_net:'ElasticNet',lightgbm:'LightGBM',deep:'深度学习(MLP)'};

function fmtPct(x,n=2){return (x==null)?'—':(x*100).toFixed(n)+'%';}
function fmtNum(x,n=2){return (x==null)?'—':x.toFixed(n);}
function cls(x){return x>=0?'pos':'neg';}
function hexA(hex,a){const h=hex.replace('#','');const r=parseInt(h.substring(0,2),16),g=parseInt(h.substring(2,4),16),b=parseInt(h.substring(4,6),16);return `rgba(${r},${g},${b},${a})`;}
function grad(color,a0,a1){return new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:hexA(color,a0)},{offset:1,color:hexA(color,a1)}]);}

// ---- meta ----
const m = DATA.meta||{};
document.getElementById('meta').innerHTML =
  `<span class="badge">数据源 ${m.data_source||'—'}</span>`+
  `<span class="badge">样本 ${m.start_date} ~ ${m.end_date}</span>`+
  `<span class="badge">股票池 ${m.universe_size||'—'}</span>`+
  `<span class="badge">因子 ${m.n_factors||'—'}</span>`+
  `<span class="badge">模型 ${((m.models)||[]).join('/')}</span>`+
  `<span class="badge">扩张窗口 ${m.n_folds||'—'} 折</span>`+
  `<span class="badge">生成 ${m.generated_at||'—'}</span>`;

// ---- KPI ----
const nav = DATA.model_nav||{};
function bestBy(key,hi=true){
  let best=null;
  for(const k in nav){const v=nav[k].perf; if(best==null||(hi? v[key]>best.v[key] : v[key]<best.v[key])) best={k,v};}
  return best;
}
const bestSharpe = bestBy('sharpe',true);
const bestRet = bestBy('annual_return',true);
const ic = (DATA.ic_summary||[]).slice().sort((a,b)=>Math.abs(b.ir)-Math.abs(a.ir));
const topFactor = ic[0]||{};
const kpiAccent = [C.cyan, C.bear, C.amber, C.violet];
const kpis = [
  {label:`最佳夏普模型 (${MODEL_LABEL[bestSharpe.k]||bestSharpe.k})`,
   val:fmtNum(bestSharpe.v.sharpe,2), meta:`年化 ${fmtPct(bestSharpe.v.annual_return)} · 最大回撤 ${fmtPct(bestSharpe.v.max_drawdown)}`, c:C.cyan},
  {label:`最高年化模型 (${MODEL_LABEL[bestRet.k]||bestRet.k})`,
   val:fmtPct(bestRet.v.annual_return), meta:`Calmar ${fmtNum(bestRet.v.calmar)} · 波动 ${fmtPct(bestRet.v.annual_vol)}`, c:C.bear},
  {label:'Top 因子 (按 |IC_IR|)',
   val:topFactor.factor||'—', meta:`IC_IR ${fmtNum(topFactor.ir,3)} · |IC| ${fmtNum(topFactor.abs_ic_mean,3)}`, c:C.amber},
  {label:'最强模型最大回撤',
   val:fmtPct(bestSharpe.v.max_drawdown), meta:`Calmar ${fmtNum(bestSharpe.v.calmar)} · 样本外验证`, c:C.violet},
];
document.getElementById('kpis').innerHTML = kpis.map((k,i)=>
  `<div class="glass kpi"><div class="accent" style="background:linear-gradient(90deg,${k.c},transparent)"></div>`+
  `<div class="label">${k.label}</div><div class="val num" style="color:${k.c}">${k.val}</div><div class="meta">${k.meta}</div></div>`).join('');

// ---- NAV chart ----
const navChart = echarts.init(document.getElementById('navChart'),'factorlab');
const models = Object.keys(nav);
let baseDates = Object.keys(nav[models[0]].nav).sort();
const seriesNav = models.map(k=>{
  const mp = nav[k].nav;
  const color = MODEL_COLORS[k]||'#888';
  const vals = baseDates.map(d=> mp[d]!=null ? +mp[d].toFixed(4) : null);
  return {name:MODEL_LABEL[k]||k, type:'line', showSymbol:false, smooth:true,
    lineStyle:{width:2.4,color,shadowColor:color,shadowBlur:10}, itemStyle:{color},
    areaStyle:{color:grad(color,0.10,0)}, data:vals};
});
navChart.setOption({
  backgroundColor:'transparent',
  tooltip:{trigger:'axis',axisPointer:{type:'line',lineStyle:{color:'#334155'}}},
  legend:{textStyle:{color:C.muted},top:0},
  grid:{left:54,right:20,top:36,bottom:30},
  xAxis:{type:'category',data:baseDates,axisLabel:{color:C.muted},axisLine:{lineStyle:{color:C.line}}},
  yAxis:{type:'value',scale:true,axisLabel:{color:C.muted,formatter:v=>v.toFixed(2)},splitLine:{lineStyle:{color:C.line}}},
  series:[...seriesNav,{type:'line',data:[],markLine:{silent:true,symbol:'none',lineStyle:{color:'#475569',type:'dashed',width:1},data:[{yAxis:1}],label:{show:false}}}]
});

// ---- IC table ----
const tb = document.querySelector('#icTable tbody');
tb.innerHTML = ic.map(r=>{
  const irCls = r.ir>=0?'pos':'neg';
  return `<tr><td>${r.factor}</td><td>${r.method}</td>`+
    `<td class="${cls(r.ic_mean)} num">${fmtNum(r.ic_mean,3)}</td>`+
    `<td class="num">${fmtNum(r.abs_ic_mean,3)}</td>`+
    `<td class="${irCls} num">${fmtNum(r.ir,3)}</td>`+
    `<td class="num">${fmtPct(r.ic_pos_ratio,1)}</td></tr>`;
}).join('');

// ---- decay heatmap ----
const decay = DATA.factor_decay||{};
const fkeys = Object.keys(decay);
const maxLag = fkeys.length? Math.max(...fkeys.map(f=>decay[f].length)) : 0;
const hd=[]; let dmax=-1e9,dmin=1e9;
fkeys.forEach((f,fi)=>{
  decay[f].forEach(p=>{const v=p.ic; hd.push([p.lag-1,fi,+v.toFixed(3)]); if(v>dmax)dmax=v; if(v<dmin)dmin=v;});
});
const decayChart = echarts.init(document.getElementById('decayChart'),'factorlab');
decayChart.setOption({
  backgroundColor:'transparent',
  tooltip:{position:'top',formatter:p=>`${fkeys[p.value[1]]} · lag ${p.value[0]+1}<br/>RankIC: <b>${p.value[2]}</b>`},
  grid:{left:80,right:20,top:20,bottom:60},
  xAxis:{type:'category',data:Array.from({length:maxLag},(_,i)=>i+1),name:'滞后(天)',
    axisLabel:{color:C.muted},axisLine:{lineStyle:{color:C.line}}},
  yAxis:{type:'category',data:fkeys,axisLabel:{color:C.muted},axisLine:{lineStyle:{color:C.line}}},
  visualMap:{min:dmin,max:dmax,calculable:true,orient:'horizontal',
    left:'center',bottom:10,textStyle:{color:C.muted},itemWidth:12,itemHeight:160,
    inRange:{color:['#1d4ed8','#0b1220','#f43f5e']}},
  series:[{type:'heatmap',data:hd,itemStyle:{borderColor:'#0a0f1c',borderWidth:2,borderRadius:4},emphasis:{itemStyle:{borderColor:'#fff',borderWidth:1}}}]
});

// ---- group long-short (top factor) ----
const gr = DATA.group_returns||{};
const topF = topFactor.factor && gr[topFactor.factor] ? topFactor.factor : (Object.keys(gr)[0]||null);
const groupChart = echarts.init(document.getElementById('groupChart'),'factorlab');
if(topF){
  const g = gr[topF];
  const dates = g.long_short.dates;
  const gs = ['G1','G2','G3','G4','G5'];
  const palette=[C.bear,'#7dd3a0','#9aa7b8','#f0a',C.bull];
  const s = gs.map((gn,i)=>({name:gn,type:'line',showSymbol:false,smooth:true,
    lineStyle:{width:1.5,color:palette[i]},data:g.groups[gn].values.map(v=>+v.toFixed(4))}));
  s.push({name:'多空(L-S)',type:'line',showSymbol:false,smooth:true,
    lineStyle:{width:3,color:C.violet,shadowColor:C.violet,shadowBlur:12},itemStyle:{color:C.violet},
    areaStyle:{color:grad(C.violet,0.14,0)},data:g.long_short.values.map(v=>+v.toFixed(4))});
  groupChart.setOption({
    backgroundColor:'transparent',tooltip:{trigger:'axis',axisPointer:{type:'line',lineStyle:{color:'#334155'}}},legend:{textStyle:{color:C.muted},top:0},
    grid:{left:55,right:20,top:36,bottom:30},
    xAxis:{type:'category',data:dates,axisLabel:{color:C.muted},axisLine:{lineStyle:{color:C.line}}},
    yAxis:{type:'value',scale:true,axisLabel:{color:C.muted},splitLine:{lineStyle:{color:C.line}}},
    series:s
  });
  document.getElementById('groupNote').textContent =
    `因子 ${topF} 按因子值分为 5 组（G1 最低 → G5 最高），多空组合 = G5 做多 − G1 做空；曲线为累计净值。`;
}else{
  document.getElementById('groupNote').textContent='无分组数据。';
}

// ---- cost robustness ----
const cost = DATA.cost_scenarios||{};
const bps = Object.keys(cost).map(Number).sort((a,b)=>a-b);
const costChart = echarts.init(document.getElementById('costChart'),'factorlab');
const cm = Object.keys(nav);
const cs = cm.map(k=>{const color=MODEL_COLORS[k]||'#888';return {name:MODEL_LABEL[k]||k,type:'line',showSymbol:true,symbolSize:7,smooth:true,
  lineStyle:{width:2.4,color,shadowColor:color,shadowBlur:8},itemStyle:{color},
  data:bps.map(b=> cost[b] && cost[b][k] ? +cost[b][k].annual_return.toFixed(4):null)};});
costChart.setOption({
  backgroundColor:'transparent',tooltip:{trigger:'axis',valueFormatter:v=>(v==null?'—':(v*100).toFixed(1)+'%')},
  legend:{textStyle:{color:C.muted},top:0},
  grid:{left:55,right:20,top:36,bottom:40},
  xAxis:{type:'category',data:bps.map(b=>b+'bps'),name:'双边成本',axisLabel:{color:C.muted},axisLine:{lineStyle:{color:C.line}}},
  yAxis:{type:'value',axisLabel:{color:C.muted,formatter:v=>(v*100).toFixed(0)+'%'},splitLine:{lineStyle:{color:C.line}}},
  series:cs
});

// ---- robustness bull/neutral/bear ----
const rob = DATA.robustness||{};
const rk = Object.keys(rob);
const mkSeries=(key,color)=>({name:key,type:'bar',itemStyle:{color,borderRadius:[4,4,0,0]},
  data:rk.map(k=> rob[k][key]? +rob[k][key].annual_return.toFixed(4):null)});
const robChart = echarts.init(document.getElementById('robChart'),'factorlab');
robChart.setOption({
  backgroundColor:'transparent',tooltip:{trigger:'axis',valueFormatter:v=>(v==null?'—':(v*100).toFixed(0)+'%')},
  legend:{textStyle:{color:C.muted},top:0},
  grid:{left:55,right:20,top:36,bottom:30},
  xAxis:{type:'category',data:rk.map(k=>MODEL_LABEL[k]||k),axisLabel:{color:C.muted},axisLine:{lineStyle:{color:C.line}}},
  yAxis:{type:'value',axisLabel:{color:C.muted,formatter:v=>(v*100).toFixed(0)+'%'},splitLine:{lineStyle:{color:C.line}}},
  series:[mkSeries('bull',C.bull),mkSeries('neutral',C.cyan),mkSeries('bear',C.bear)]
});

document.getElementById('footer').innerHTML =
  '本报告由 FactorLab 自动生成 · 研究用途，非投资建议。'+
  '所有结果均基于样本外（OOS）扩张窗口验证，因子打分隔日换仓并扣除交易成本。'+
  '数据源：'+(m.data_source||'—')+'（默认确定性合成数据，接入 AkShare 后可用于真实 A 股数据）。';

window.addEventListener('resize',()=>{[navChart,decayChart,groupChart,costChart,robChart].forEach(c=>c.resize());});
</script>
</body>
</html>
"""


def _self_test() -> None:
    """开发期冒烟：用内置最小结构验证模板可渲染。"""
    sample = {
        "meta": {"data_source": "synthetic", "start_date": "2018", "end_date": "2025",
                 "universe_size": 30, "n_factors": 2, "models": ["eq_weight", "deep"],
                 "n_folds": 5, "generated_at": "x"},
        "model_nav": {"eq_weight": {"nav": {"2020-01-01": 1.0, "2020-01-02": 1.01},
                                    "perf": {"annual_return": 0.17, "annual_vol": 0.07, "sharpe": 2.2,
                                             "max_drawdown": -0.05, "calmar": 3.0}}},
        "ic_summary": [{"factor": "ep", "method": "pearson", "ic_mean": 0.02, "ic_std": 0.1,
                        "ir": 0.2, "ic_pos_ratio": 0.55, "abs_ic_mean": 0.08}],
        "factor_decay": {"ep": [{"lag": 1, "ic": 0.05}, {"lag": 2, "ic": 0.03}]},
        "group_returns": {"ep": {"long_short": {"dates": ["2020-01-01"], "values": [1.0]},
                                 "groups": {"G1": {"dates": ["2020-01-01"], "values": [1.0]}}}},
        "cost_scenarios": {"0.0": {"eq_weight": {"annual_return": 0.17, "sharpe": 2.2}},
                           "10.0": {"eq_weight": {"annual_return": 0.15, "sharpe": 2.0}}},
        "robustness": {"eq_weight": {"bull": {"annual_return": 0.3}, "neutral": {"annual_return": 0.1},
                                     "bear": {"annual_return": -0.05}}},
    }
    out = build_report(sample, Path("/tmp/_report_selftest.html"))
    txt = out.read_text(encoding="utf-8")
    assert "__DATA__" not in txt, "占位符未替换"
    assert "echarts" in txt
    assert "__ECHARTS_THEME__" not in txt, "主题占位符未替换"
    print("report self-test OK ->", out)


if __name__ == "__main__":
    _self_test()
