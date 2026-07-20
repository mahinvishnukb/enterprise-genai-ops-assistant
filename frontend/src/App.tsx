import { useState, useRef, useEffect, useCallback } from "react";
import {
  BarChart, Bar, PieChart, Pie, Cell, AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip as RCTooltip, Legend,
  ResponsiveContainer, ComposedChart, Line,
} from "recharts";
import { sendChatMessage, uploadDocument, fetchStats, fetchDocuments, ChatResponse, StatsResponse, DocumentInfo as ServerDoc } from "./api";
import {
  MessageSquare, Database, BarChart2, FileText, History,
  Send, Upload, Zap, Brain, ChevronRight, ChevronDown,
  Loader2, CheckCircle, X, AlertCircle, Plus, Search,
  Settings, ArrowUpDown, Layers, Hash, Clock, Activity,
  Terminal, FolderOpen, File, RefreshCw,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────
type Message = { id: number; role: "user"|"assistant"; text: string; meta?: ChatResponse; ts: number; error?: boolean };
type Tab = "chat" | "query" | "analytics" | "documents" | "history" | "stats";
type UploadedDoc = { name: string; chunks: number; ts: number };
type QueryRecord = { id: number; q: string; agent: string; ts: number; result?: ChatResponse };

let uid = 0;
const now = () => Date.now();
const fmt = (ms: number) => new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const fmtDate = (ms: number) => new Date(ms).toLocaleDateString([], { month: "short", day: "numeric" });

// ─── Agent config ─────────────────────────────────────────────────────────────
const AGENTS: Record<string, { color: string; bg: string; label: string; dot: string }> = {
  sql_agent:          { color: "text-sky-400",     bg: "bg-sky-900/30",     label: "SQL",         dot: "bg-sky-400" },
  analytics_agent:    { color: "text-emerald-400", bg: "bg-emerald-900/30", label: "Analytics",   dot: "bg-emerald-400" },
  knowledge_agent:    { color: "text-violet-400",  bg: "bg-violet-900/30",  label: "Knowledge",   dot: "bg-violet-400" },
  conversation_agent: { color: "text-gray-400",    bg: "bg-gray-800/30",    label: "Assistant",   dot: "bg-gray-400" },
};

// ─── Micro components ─────────────────────────────────────────────────────────
function Dot({ agent }: { agent: string }) {
  return <span className={`inline-block w-1.5 h-1.5 rounded-full ${AGENTS[agent]?.dot ?? "bg-gray-500"}`} />;
}

function AgentTag({ agent }: { agent: string }) {
  const a = AGENTS[agent] ?? AGENTS.conversation_agent;
  return (
    <span className={`inline-flex items-center gap-1 text-[9px] font-bold uppercase tracking-widest px-1.5 py-0.5 rounded ${a.bg} ${a.color} border border-current/20`}>
      <Dot agent={agent} />{a.label}
    </span>
  );
}

function MarkdownText({ text }: { text: string }) {
  const html = text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em class="text-gray-300">$1</em>')
    .replace(/^• (.+)$/gm, '<li class="ml-4 list-disc text-gray-300 leading-relaxed">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 list-decimal text-gray-300 leading-relaxed">$2</li>')
    .replace(/`([^`]+)`/g, '<code class="bg-gray-800 text-emerald-400 px-1 py-0.5 rounded text-[11px] font-mono">$1</code>')
    .replace(/\n\n/g, '</p><p class="mt-2 leading-relaxed">')
    .replace(/\n/g, '<br/>');
  return <div className="text-[13px] text-gray-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: `<p class="leading-relaxed">${html}</p>` }} />;
}

function MetricsGrid({ metrics }: { metrics: Record<string, string|number> }) {
  return (
    <div className="grid grid-cols-2 gap-1.5 mt-3">
      {Object.entries(metrics).map(([k, v]) => (
        <div key={k} className="bg-gray-900 border border-gray-700/40 rounded px-3 py-2">
          <p className="text-[9px] text-gray-500 uppercase tracking-widest font-semibold">{k}</p>
          <p className="text-sm font-bold text-white mt-0.5 font-mono">{String(v)}</p>
        </div>
      ))}
    </div>
  );
}

function DataTable({ rows }: { rows: Record<string, unknown>[] }) {
  const [sort, setSort] = useState<string|null>(null);
  const [dir, setDir] = useState<"asc"|"desc">("asc");
  const [page, setPage] = useState(0);
  const PER = 6;
  if (!rows.length) return <p className="text-[11px] text-gray-600 italic mt-2">No rows returned.</p>;
  const cols = Object.keys(rows[0]);
  const sorted = [...rows].sort((a, b) => {
    if (!sort) return 0;
    return dir === "asc"
      ? String(a[sort] ?? "").localeCompare(String(b[sort] ?? ""), undefined, { numeric: true })
      : String(b[sort] ?? "").localeCompare(String(a[sort] ?? ""), undefined, { numeric: true });
  });
  const pages = Math.ceil(sorted.length / PER);
  const visible = sorted.slice(page * PER, (page + 1) * PER);
  return (
    <div className="mt-2">
      <div className="overflow-x-auto rounded border border-gray-700/40">
        <table className="min-w-full text-[11px]">
          <thead className="bg-gray-800/80">
            <tr>{cols.map(c => (
              <th key={c} onClick={() => { sort === c ? setDir(d => d === "asc" ? "desc" : "asc") : setSort(c); setPage(0); }}
                className="px-3 py-2 text-left text-gray-400 font-semibold uppercase tracking-wider cursor-pointer hover:text-gray-200 select-none whitespace-nowrap">
                <span className="flex items-center gap-1">{c}<ArrowUpDown size={8} className={sort === c ? "text-sky-400" : "opacity-30"} /></span>
              </th>
            ))}</tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {visible.map((row, i) => (
              <tr key={i} className="hover:bg-gray-800/30 transition-colors">
                {cols.map(c => (
                  <td key={c} className="px-3 py-1.5 text-gray-300 font-mono whitespace-nowrap">{String(row[c] ?? "—")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center justify-between mt-1.5 text-[10px] text-gray-500">
          <span>{rows.length} rows</span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(p => Math.max(0, p-1))} disabled={page === 0} className="px-1.5 py-0.5 bg-gray-800 rounded hover:bg-gray-700 disabled:opacity-30">‹</button>
            <span>{page+1}/{pages}</span>
            <button onClick={() => setPage(p => Math.min(pages-1, p+1))} disabled={page === pages-1} className="px-1.5 py-0.5 bg-gray-800 rounded hover:bg-gray-700 disabled:opacity-30">›</button>
          </div>
        </div>
      )}
    </div>
  );
}

function SQLViewer({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  // Highlight keywords first, then string literals.
  // NOTE: do NOT run a number regex after inserting HTML — it would match
  // "400" inside class="text-sky-400" and corrupt the output.
  const hl = sql
    .replace(/\b(SELECT|FROM|WHERE|ORDER BY|GROUP BY|LIMIT|JOIN|ON|AND|OR|HAVING|AS|COUNT|AVG|SUM|DISTINCT|ROUND|CASE|WHEN|THEN|ELSE|END)\b/g, '<span class="text-sky-400 font-bold">$1</span>')
    .replace(/('[^']*')/g, '<span class="text-amber-400">$1</span>');
  return (
    <div className="mt-2">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 font-mono transition-colors">
        {open ? <ChevronDown size={10}/> : <ChevronRight size={10}/>}generated sql
      </button>
      {open && <pre className="mt-1 p-3 bg-gray-950 border border-gray-800 rounded text-[11px] text-gray-300 overflow-x-auto leading-relaxed font-mono" dangerouslySetInnerHTML={{ __html: hl }} />}
    </div>
  );
}

// ─── Chart layer ──────────────────────────────────────────────────────────────
const CP = ['#6366f1','#38bdf8','#34d399','#a78bfa','#fbbf24','#fb923c','#f87171','#e879f9'];
const STATUS_CLR: Record<string,string> = {
  Delivered:'#34d399','Minor Delay':'#fbbf24',Delayed:'#fb923c','Critical Delay':'#f87171',
};
const RISK_CLR: Record<string,string> = {Low:'#34d399',Medium:'#fbbf24',High:'#fb923c',Critical:'#f87171'};
const GRID = '#1f2937';
const TICK = { fill:'#6b7280', fontSize: 9 };

function ChartTip({ active, payload, label }: { active?: boolean; payload?: {name:string;value:unknown;color?:string;fill?:string}[]; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-gray-950 border border-gray-700/60 rounded-lg px-3 py-2.5 shadow-xl text-[11px] font-mono max-w-[220px]">
      {label && <p className="text-gray-400 mb-1.5 text-[9px] uppercase tracking-widest">{label}</p>}
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color ?? p.fill ?? '#fff' }} className="leading-relaxed">
          <span className="text-gray-500">{p.name}: </span>
          <span className="font-bold">
            {typeof p.value === 'number'
              ? Number.isInteger(p.value) ? p.value.toLocaleString() : p.value.toFixed(2)
              : String(p.value)}
          </span>
        </p>
      ))}
    </div>
  );
}

function SmartChart({ rows, analysisType }: { rows: Record<string,unknown>[]; analysisType?: string }) {
  if (!rows?.length) return null;
  const H = 220;

  if (analysisType === 'carrier_analysis') {
    return (
      <ResponsiveContainer width="100%" height={H}>
        <ComposedChart data={rows} margin={{ top:4, right:28, bottom:24, left:0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="carrier" tick={TICK} />
          <YAxis yAxisId="pct" domain={[55,90]} tick={TICK} unit="%" width={32} />
          <YAxis yAxisId="hrs" orientation="right" tick={TICK} unit="h" width={28} />
          <RCTooltip content={<ChartTip />} />
          <Legend wrapperStyle={{ fontSize:10, color:'#6b7280', paddingTop:4 }} />
          <Bar yAxisId="pct" dataKey="on_time_pct" name="On-time %" fill="#6366f1" radius={[3,3,0,0]} maxBarSize={36} />
          <Line yAxisId="hrs" type="monotone" dataKey="avg_delay_hours" name="Avg delay (h)" stroke="#f87171" strokeWidth={2} dot={{ fill:'#f87171', r:3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  if (analysisType === 'kpi_summary') {
    const pctLabel = ({ percent }: { percent?: number }) =>
      (percent ?? 0) < 0.06 ? '' : `${((percent??0)*100).toFixed(0)}%`;
    return (
      <ResponsiveContainer width="100%" height={H}>
        <PieChart>
          <Pie data={rows} dataKey="count" nameKey="shipment_status" cx="50%" cy="48%"
            outerRadius={82} innerRadius={38} paddingAngle={2} label={pctLabel} labelLine={false}>
            {rows.map((r, i) => (
              <Cell key={i} fill={STATUS_CLR[r.shipment_status as string] ?? CP[i % CP.length]} />
            ))}
          </Pie>
          <RCTooltip content={<ChartTip />} />
          <Legend wrapperStyle={{ fontSize:9, color:'#6b7280' }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (analysisType === 'risk_analysis') {
    const pctLabel = ({ percent }: { percent?: number }) =>
      (percent ?? 0) < 0.06 ? '' : `${((percent??0)*100).toFixed(0)}%`;
    return (
      <ResponsiveContainer width="100%" height={H}>
        <PieChart>
          <Pie data={rows} dataKey="count" nameKey="risk_category" cx="50%" cy="48%"
            outerRadius={82} innerRadius={38} paddingAngle={2} label={pctLabel} labelLine={false}>
            {rows.map((r, i) => (
              <Cell key={i} fill={RISK_CLR[r.risk_category as string] ?? CP[i % CP.length]} />
            ))}
          </Pie>
          <RCTooltip content={<ChartTip />} />
          <Legend wrapperStyle={{ fontSize:9, color:'#6b7280' }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  if (analysisType === 'incident_analysis') {
    const data = rows.map(r => ({
      ...r,
      _label: (r.incident_type as string)?.split(' ').slice(0,2).join(' ') ?? String(r.incident_type),
    }));
    return (
      <ResponsiveContainer width="100%" height={H}>
        <BarChart data={data} margin={{ top:4, right:8, bottom:44, left:0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="_label" tick={{ fill:'#6b7280', fontSize:8 }} angle={-30} textAnchor="end" interval={0} />
          <YAxis tick={TICK} width={36} />
          <RCTooltip content={<ChartTip />} />
          <Legend wrapperStyle={{ fontSize:10, color:'#6b7280' }} />
          <Bar dataKey="count" name="Incidents" radius={[3,3,0,0]} maxBarSize={44}>
            {data.map((_, i) => <Cell key={i} fill={CP[i % CP.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (analysisType === 'trend_analysis') {
    const data = [...rows].reverse();
    return (
      <ResponsiveContainer width="100%" height={H}>
        <AreaChart data={data} margin={{ top:4, right:28, bottom:16, left:0 }}>
          <defs>
            <linearGradient id="gShip" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#6366f1" stopOpacity={0.35}/>
              <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
            </linearGradient>
            <linearGradient id="gPct" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#34d399" stopOpacity={0.35}/>
              <stop offset="95%" stopColor="#34d399" stopOpacity={0}/>
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="month" tick={{ fill:'#6b7280', fontSize:8 }} />
          <YAxis yAxisId="cnt" tick={TICK} width={36} />
          <YAxis yAxisId="pct" orientation="right" tick={TICK} unit="%" width={32} />
          <RCTooltip content={<ChartTip />} />
          <Legend wrapperStyle={{ fontSize:10, color:'#6b7280' }} />
          <Area yAxisId="cnt" type="monotone" dataKey="shipments" name="Shipments" stroke="#6366f1" fill="url(#gShip)" strokeWidth={2} />
          <Area yAxisId="pct" type="monotone" dataKey="on_time_pct" name="On-time %" stroke="#34d399" fill="url(#gPct)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (analysisType === 'delay_analysis' || analysisType === 'critical_delay_analysis' || analysisType === 'route_analysis') {
    const hasRoute = 'destination' in (rows[0] ?? {});
    const yKey = hasRoute ? 'route' : 'origin';
    const xKey = analysisType === 'route_analysis' ? 'shipments'
      : analysisType === 'critical_delay_analysis' ? 'critical_delays'
      : 'avg_delay_hours';
    const data = rows.slice(0,8).map(r => ({
      ...r,
      route: hasRoute ? `${r.origin}→${r.destination}` : r.origin,
    }));
    const barH = Math.max(180, data.length * 30);
    return (
      <ResponsiveContainer width="100%" height={barH}>
        <BarChart layout="vertical" data={data} margin={{ top:4, right:16, bottom:4, left:4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
          <XAxis type="number" tick={{ fill:'#6b7280', fontSize:8 }} />
          <YAxis dataKey={yKey} type="category" tick={{ fill:'#6b7280', fontSize:8 }} width={110} />
          <RCTooltip content={<ChartTip />} />
          <Bar dataKey={xKey} name={xKey.replace(/_/g,' ')} radius={[0,3,3,0]} maxBarSize={20}>
            {data.map((_,i) => <Cell key={i} fill={i===0?'#f87171':i===1?'#fb923c':i===2?'#fbbf24':'#6366f1'} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    );
  }

  if (analysisType === 'weather_impact') {
    return (
      <ResponsiveContainer width="100%" height={H}>
        <ComposedChart data={rows} margin={{ top:4, right:28, bottom:20, left:0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
          <XAxis dataKey="weather_condition" tick={{ fill:'#6b7280', fontSize:8 }} />
          <YAxis yAxisId="hrs" tick={TICK} unit="h" width={32} />
          <YAxis yAxisId="pct" orientation="right" tick={TICK} unit="%" width={32} />
          <RCTooltip content={<ChartTip />} />
          <Legend wrapperStyle={{ fontSize:10, color:'#6b7280' }} />
          <Bar yAxisId="hrs" dataKey="avg_delay_hours" name="Avg delay (h)" fill="#fbbf24" radius={[3,3,0,0]} maxBarSize={44} />
          <Line yAxisId="pct" type="monotone" dataKey="on_time_pct" name="On-time %" stroke="#34d399" strokeWidth={2} dot={{ fill:'#34d399', r:3 }} />
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  // Generic fallback: auto-detect first string col as X, up to 3 numeric cols as bars
  const cols = Object.keys(rows[0] ?? {});
  const xCol = cols.find(c => typeof rows[0][c] === 'string') ?? cols[0];
  const yCols = cols.filter(c => typeof rows[0][c] === 'number').slice(0,3);
  if (!yCols.length) return null;
  return (
    <ResponsiveContainer width="100%" height={H}>
      <BarChart data={rows.slice(0,15)} margin={{ top:4, right:8, bottom:20, left:0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
        <XAxis dataKey={xCol} tick={{ fill:'#6b7280', fontSize:8 }} />
        <YAxis tick={TICK} width={36} />
        <RCTooltip content={<ChartTip />} />
        <Legend wrapperStyle={{ fontSize:10, color:'#6b7280' }} />
        {yCols.map((k,i) => (
          <Bar key={k} dataKey={k} name={k.replace(/_/g,' ')} fill={CP[i%CP.length]} radius={[3,3,0,0]} maxBarSize={44} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

function ChartAndTable({ rows, analysisType }: { rows: Record<string,unknown>[]; analysisType?: string }) {
  const [view, setView] = useState<'chart'|'table'>('chart');
  return (
    <div className="mt-3 border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-gray-800 bg-gray-900/60">
        <span className="text-[9px] text-indigo-400/80 uppercase tracking-widest flex-1 font-mono">
          {analysisType?.replace(/_/g,' ') ?? 'visualization'}
        </span>
        {(['chart','table'] as const).map(v => (
          <button key={v} onClick={() => setView(v)}
            className={`text-[9px] px-2 py-0.5 rounded font-mono transition-colors ${
              view===v ? 'bg-indigo-600/25 text-indigo-300' : 'text-gray-600 hover:text-gray-400'}`}>
            {v==='chart' ? '◈ chart' : '⊞ table'}
          </button>
        ))}
      </div>
      <div className="p-3 bg-gray-950/30">
        {view==='chart'
          ? <SmartChart rows={rows} analysisType={analysisType} />
          : <DataTable rows={rows} />}
      </div>
    </div>
  );
}

// ─── Analytics dashboard cards ─────────────────────────────────────────────────
const DASH_CARDS = [
  { id:'carrier',  title:'Carrier Performance', desc:'On-time rates & delays by carrier',      q:'Carrier performance breakdown', icon: BarChart2 },
  { id:'status',   title:'Shipment Status',     desc:'Distribution of delivery outcomes',     q:'KPI summary and status breakdown', icon: Layers },
  { id:'delay',    title:'Delay Hotspots',      desc:'Routes with highest average delays',    q:'Which routes have the most delays?', icon: AlertCircle },
  { id:'incident', title:'Incident Analysis',   desc:'Types and frequency of incidents',      q:'What are the top incident types and their financial impact?', icon: X },
  { id:'weather',  title:'Weather Impact',      desc:'How weather affects delivery time',     q:'What is the weather impact on delays?', icon: Activity },
  { id:'risk',     title:'Risk Distribution',   desc:'Shipment risk category breakdown',      q:'Show risk category breakdown', icon: Hash },
] as const;

function ChartCard({ title, desc, query, icon: Icon, onAskInChat }:{
  title:string; desc:string; query:string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  onAskInChat:(q:string)=>void;
}) {
  const [data, setData] = useState<ChatResponse|null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState(false);

  const load = async () => {
    setLoading(true); setErr(false);
    try {
      const r = await sendChatMessage(query, []);
      setData(r);
    } catch { setErr(true); }
    finally { setLoading(false); }
  };

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center gap-2 px-3 py-2 bg-gray-900/60 border-b border-gray-800">
        <Icon size={12} className="text-indigo-400 shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] text-gray-200 font-semibold leading-tight">{title}</p>
          <p className="text-[9px] text-gray-600 leading-tight">{desc}</p>
        </div>
        <button onClick={() => onAskInChat(query)}
          className="text-[9px] text-indigo-400 hover:text-indigo-300 font-mono whitespace-nowrap transition-colors ml-1">
          ask in chat →
        </button>
      </div>
      <div className="p-3 bg-gray-950/30">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-[160px] gap-2">
            <Loader2 size={18} className="animate-spin text-indigo-400" />
            <p className="text-[10px] text-gray-500 font-mono">Fetching data…</p>
          </div>
        ) : data?.rows?.length ? (
          <SmartChart rows={data.rows} analysisType={data.analysis_type} />
        ) : (
          <button onClick={load}
            className={`w-full h-[80px] border border-dashed rounded-lg text-[10px] font-mono transition-all
              ${err
                ? 'border-red-800/60 text-red-600 hover:border-red-700 hover:text-red-400'
                : 'border-gray-700/50 text-gray-600 hover:border-indigo-800/60 hover:text-indigo-400'}`}>
            {err ? '⚠ retry load' : '+ load chart'}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Message bubble ────────────────────────────────────────────────────────────
function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === "user") return (
    <div className="flex justify-end mb-4 group">
      <div className="max-w-[88%] sm:max-w-[72%]">
        <div className="bg-indigo-600/90 text-white rounded-lg rounded-br-sm px-3 py-2 sm:px-4 sm:py-2.5 text-[12px] sm:text-[13px] leading-relaxed">{msg.text}</div>
        <p className="text-[9px] text-gray-600 text-right mt-1 opacity-0 group-hover:opacity-100 transition-opacity">{fmt(msg.ts)}</p>
      </div>
    </div>
  );

  const a = msg.meta ? AGENTS[msg.meta.agent] : null;
  return (
    <div className="flex gap-2.5 mb-4 group">
      <div className="w-6 h-6 rounded bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0 mt-0.5">
        <Zap size={11} />
      </div>
      <div className="flex-1 min-w-0">
        {msg.meta && (
          <div className="flex items-center gap-2 mb-1.5 flex-wrap">
            <AgentTag agent={msg.meta.agent} />
            <span className="text-[9px] text-gray-600 font-mono">router → {msg.meta.agent} → done</span>
            {msg.meta.routing?.ambiguous && (
              <span className="inline-flex items-center gap-1 text-[9px] text-amber-400 font-mono">
                <AlertCircle size={9} />ambiguous · also checked {msg.meta.routing.also_considered}
              </span>
            )}
          </div>
        )}
        <div className={`rounded-lg rounded-tl-sm px-4 py-3 border ${
          msg.error ? "bg-red-950/40 border-red-800/40" :
          a ? `${a.bg} border-gray-700/30` : "bg-gray-800/50 border-gray-700/30"
        }`}>
          {msg.meta?.agent === "sql_agent" && (
            <>
              <p className="text-[11px] text-gray-400 mb-1.5 font-mono">
                <span className="text-white font-bold">{msg.meta.row_count}</span> rows returned
              </p>
              {msg.meta.rows && <DataTable rows={msg.meta.rows} />}
              {msg.meta.sql && <SQLViewer sql={msg.meta.sql} />}
            </>
          )}
          {msg.meta?.agent === "analytics_agent" && (
            <>
              {msg.text && <MarkdownText text={msg.text} />}
              {msg.meta.metrics && <MetricsGrid metrics={msg.meta.metrics} />}
              {msg.meta.rows && msg.meta.rows.length > 0 && (
                <ChartAndTable rows={msg.meta.rows} analysisType={msg.meta.analysis_type} />
              )}
            </>
          )}
          {(!msg.meta || msg.meta.agent === "knowledge_agent" || msg.meta.agent === "conversation_agent") && (
            <>
              <MarkdownText text={msg.text} />
              {msg.meta?.sources && msg.meta.sources.length > 0 && (
                <div className="mt-2 pt-2 border-t border-gray-700/30">
                  <p className="text-[9px] text-gray-500 uppercase tracking-widest mb-1">sources</p>
                  <div className="flex flex-wrap gap-1">
                    {msg.meta.sources.map(s => (
                      <span key={s.chunk_id} className="inline-flex items-center gap-1 text-[9px] bg-gray-800 border border-gray-700/30 rounded px-1.5 py-0.5 text-gray-400 font-mono">
                        <File size={8}/>{s.doc_id} <span className="text-gray-600">{s.score.toFixed(2)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
        <p className="text-[9px] text-gray-600 mt-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity font-mono">{fmt(msg.ts)}</p>
      </div>
    </div>
  );
}

// ─── Panel: Documents ──────────────────────────────────────────────────────────
function DocumentsPanel({ docs, serverDocs, onUpload, uploading }: { docs: UploadedDoc[]; serverDocs: ServerDoc[]; onUpload: (f: File) => void; uploading: boolean }) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <span className="text-[10px] text-gray-400 uppercase tracking-widest font-semibold">Knowledge Base</span>
        <button onClick={() => ref.current?.click()} disabled={uploading}
          className="flex items-center gap-1 text-[10px] text-indigo-400 hover:text-indigo-300 disabled:opacity-40 transition-colors">
          {uploading ? <Loader2 size={10} className="animate-spin"/> : <Plus size={10}/>}
          {uploading ? "ingesting…" : "add file"}
        </button>
        <input ref={ref} type="file" className="hidden" accept=".txt,.pdf,.docx,.csv"
          onChange={e => { const f = e.target.files?.[0]; if (f) onUpload(f); e.target.value = ""; }} />
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {/* Built-in server docs */}
        {serverDocs.length > 0 && (
          <div className="mb-2">
            <p className="text-[9px] text-gray-600 uppercase tracking-widest px-2 py-1">Built-in</p>
            {serverDocs.map(d => (
              <div key={d.doc_id} className="flex items-start gap-2 px-2 py-2 hover:bg-gray-800/40 rounded cursor-default">
                <File size={12} className="text-emerald-400 mt-0.5 shrink-0"/>
                <div className="min-w-0">
                  <p className="text-[11px] text-gray-200 truncate">{d.doc_id.replace(/_/g, " ")}</p>
                  <p className="text-[9px] text-gray-500 font-mono">{d.chunk_count} chunks · auto-loaded</p>
                </div>
                <CheckCircle size={10} className="text-emerald-500 ml-auto mt-0.5 shrink-0"/>
              </div>
            ))}
          </div>
        )}
        {/* User-uploaded docs */}
        {docs.length > 0 && (
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-widest px-2 py-1">Uploaded</p>
            {docs.map((d, i) => (
              <div key={i} className="flex items-start gap-2 px-2 py-2 hover:bg-gray-800/40 rounded group cursor-default">
                <File size={12} className="text-violet-400 mt-0.5 shrink-0"/>
                <div className="min-w-0">
                  <p className="text-[11px] text-gray-200 truncate">{d.name}</p>
                  <p className="text-[9px] text-gray-500 font-mono">{d.chunks} chunks · {fmtDate(d.ts)}</p>
                </div>
                <CheckCircle size={10} className="text-green-500 ml-auto mt-0.5 shrink-0"/>
              </div>
            ))}
          </div>
        )}
        {serverDocs.length === 0 && docs.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <FolderOpen size={24} className="text-gray-700 mb-2"/>
            <p className="text-[11px] text-gray-600">No documents ingested</p>
            <p className="text-[10px] text-gray-700 mt-1">Upload .txt .pdf .docx .csv</p>
            <button onClick={() => ref.current?.click()}
              className="mt-3 text-[10px] text-indigo-400 hover:text-indigo-300 border border-indigo-800 rounded px-2 py-1 transition-colors">
              + Upload document
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Panel: History ────────────────────────────────────────────────────────────
function HistoryPanel({ history, onSelect }: { history: QueryRecord[]; onSelect: (q: string) => void }) {
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <span className="text-[10px] text-gray-400 uppercase tracking-widest font-semibold">Query History</span>
        <span className="text-[9px] text-gray-600 font-mono">{history.length} queries</span>
      </div>
      <div className="flex-1 overflow-y-auto p-2">
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full py-8">
            <History size={24} className="text-gray-700 mb-2"/>
            <p className="text-[11px] text-gray-600">No queries yet</p>
          </div>
        ) : [...history].reverse().map(h => (
          <button key={h.id} onClick={() => onSelect(h.q)}
            className="w-full text-left flex items-start gap-2 px-2 py-2 hover:bg-gray-800/40 rounded group transition-colors">
            <Dot agent={h.agent}/>
            <div className="min-w-0 flex-1">
              <p className="text-[11px] text-gray-300 truncate group-hover:text-white transition-colors">{h.q}</p>
              <p className="text-[9px] text-gray-600 font-mono mt-0.5">{AGENTS[h.agent]?.label} · {fmt(h.ts)}</p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Panel: Stats ──────────────────────────────────────────────────────────────
function StatsPanel({ stats }: { stats: StatsResponse | null }) {
  const items = stats ? [
    { icon: Hash, label: "DB Rows", value: stats.db_rows, color: "text-sky-400" },
    { icon: Layers, label: "Doc Chunks", value: stats.chunk_count, color: "text-violet-400" },
    { icon: Activity, label: "Queries", value: stats.queries_this_session, color: "text-emerald-400" },
  ] : [];
  return (
    <div className="flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-800">
        <span className="text-[10px] text-gray-400 uppercase tracking-widest font-semibold">System Stats</span>
      </div>
      <div className="p-3 space-y-2">
        {items.map(({ icon: Icon, label, value, color }) => (
          <div key={label} className="flex items-center justify-between px-3 py-2 bg-gray-800/40 rounded border border-gray-700/30">
            <div className="flex items-center gap-2">
              <Icon size={11} className={color}/>
              <span className="text-[11px] text-gray-400">{label}</span>
            </div>
            <span className={`text-sm font-bold font-mono ${color}`}>{value}</span>
          </div>
        ))}
        <div className="pt-2 border-t border-gray-800">
          <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-2 font-semibold">Active Agents</p>
          {Object.entries(AGENTS).map(([key, a]) => (
            <div key={key} className="flex items-center gap-2 py-1">
              <div className={`w-1.5 h-1.5 rounded-full ${a.dot}`}/>
              <span className="text-[10px] font-mono text-gray-400">{key}</span>
              <span className="ml-auto text-[9px] text-green-500">live</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState<Message[]>([{
    id: uid++, role: "assistant", ts: now(),
    text: "Welcome to the Propgatics GenAI Operations Assistant — a 4-agent system with SQL, Analytics, Knowledge, and Conversation capabilities. Ask me anything about your logistics data.",
  }]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [sidePanel, setSidePanel] = useState<"explorer"|"history"|"stats">("explorer");
  const [docs, setDocs] = useState<UploadedDoc[]>([]);
  const [serverDocs, setServerDocs] = useState<ServerDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [queryHistory, setQueryHistory] = useState<QueryRecord[]>([]);
  const [stats, setStats] = useState<StatsResponse|null>(null);
  const [sideCollapsed, setSideCollapsed] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [serverWaking, setServerWaking] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);
  useEffect(() => {
    const refresh = () => {
      fetchStats().then(setStats).catch(() => {});
      fetchDocuments().then(setServerDocs).catch(() => {});
    };
    // Warm up Render on load with retries
    const warmUp = async () => {
      for (let i = 0; i < 5; i++) {
        try {
          await fetchStats().then(setStats);
          await fetchDocuments().then(setServerDocs);
          setServerWaking(false);
          return;
        } catch {
          if (i === 0) setServerWaking(true);
          await new Promise(r => setTimeout(r, 4000));
        }
      }
      setServerWaking(false);
    };
    warmUp();
    const t = setInterval(refresh, 8000);
    return () => clearInterval(t);
  }, []);

  async function handleSend(directQuery?: string) {
    const q = (directQuery ?? input).trim();
    if (!q || loading) return;
    if (!directQuery) {
      setInput("");
      if (textRef.current) textRef.current.style.height = "auto";
    }
    setActiveTab("chat");
    const userMsg: Message = { id: uid++, role: "user", text: q, ts: now() };
    setMessages(p => [...p, userMsg]);
    setLoading(true);
    try {
      const history = messages.map(m => ({ role: m.role, text: m.text }));
      const result = await sendChatMessage(q, history);
      const text = result.agent === "sql_agent" ? `Found ${result.row_count} rows` : (result.answer ?? "");
      const assistantMsg: Message = { id: uid++, role: "assistant", text, meta: result, ts: now() };
      setMessages(p => [...p, assistantMsg]);
      setQueryHistory(p => [...p, { id: uid++, q, agent: result.agent, ts: now(), result }]);
      fetchStats().then(setStats).catch(() => {});
      fetchDocuments().then(setServerDocs).catch(() => {});
    } catch (err) {
      const msg = (err as Error).message;
      const isTimeout = msg.includes("fetch") || msg.includes("network") || msg.includes("Failed");
      setMessages(p => [...p, {
        id: uid++, role: "assistant", ts: now(), error: true,
        text: isTimeout
          ? "The server is waking up (Render free tier sleeps after 15min). Please try again in 15 seconds."
          : `Error: ${msg}`,
      }]);
    } finally {
      setLoading(false);
    }
  }

  const ingestFile = useCallback(async (file: File) => {
    setUploading(true);
    try {
      const res = await uploadDocument(file);
      setDocs(p => [...p, { name: file.name, chunks: res.chunk_count, ts: now() }]);
      setMessages(p => [...p, {
        id: uid++, role: "assistant", ts: now(),
        text: `**${file.name}** ingested — ${res.chunk_count} chunks indexed in vector store. Ready for queries.`,
      }]);
      setSidePanel("explorer");
      fetchStats().then(setStats).catch(() => {});
    } catch {
      setMessages(p => [...p, { id: uid++, role: "assistant", text: `Failed to ingest "${file.name}".`, ts: now(), error: true }]);
    } finally {
      setUploading(false);
    }
  }, []);

  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: "chat", label: "Chat", icon: <MessageSquare size={11}/> },
    { id: "query", label: "Query", icon: <Terminal size={11}/> },
    { id: "analytics", label: "Analytics", icon: <BarChart2 size={11}/> },
    { id: "documents", label: "Documents", icon: <FileText size={11}/> },
    // History/Stats also live in the desktop-only side panel, but they're
    // duplicated here as tabs so they stay reachable on phones, where the
    // activity bar and side panel are hidden for space.
    { id: "history", label: "History", icon: <History size={11}/> },
    { id: "stats", label: "Stats", icon: <Activity size={11}/> },
  ];

  const SIDE_ICONS = [
    { id: "explorer" as const, icon: <FolderOpen size={16}/>, tip: "Explorer" },
    { id: "history" as const, icon: <History size={16}/>, tip: "History" },
    { id: "stats" as const, icon: <Activity size={16}/>, tip: "Stats" },
  ];

  const suggestions = [
    "Give me a KPI summary of operations",
    "Which carrier has the best on-time rate?",
    "Show all Critical Delay shipments",
    "Which routes have the most delays?",
    "Show shipments to Vancouver",
    "What are the top incident types?",
  ];

  return (
    <div className="flex flex-col h-full bg-[#0d0d0f] text-gray-300 font-mono text-sm overflow-hidden"
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => { e.preventDefault(); setDragOver(false); const f = e.dataTransfer.files?.[0]; if (f) ingestFile(f); }}>

      {/* Server waking banner */}
      {serverWaking && (
        <div className="fixed top-0 left-0 right-0 z-50 bg-amber-900/90 border-b border-amber-700 px-4 py-2 flex items-center gap-2 text-[11px] text-amber-200 font-mono backdrop-blur-sm">
          <Loader2 size={11} className="animate-spin shrink-0"/>
          Server waking up (Render free tier sleeps after 15min of inactivity) — ready in ~15 seconds…
        </div>
      )}

      {/* Drag overlay */}
      {dragOver && (
        <div className="fixed inset-0 z-50 bg-indigo-950/90 border-2 border-dashed border-indigo-400 flex items-center justify-center backdrop-blur-sm">
          <div className="text-center">
            <Upload size={36} className="text-indigo-300 mx-auto mb-3"/>
            <p className="text-indigo-200 font-semibold font-sans">Drop to ingest</p>
          </div>
        </div>
      )}

      {/* Title bar */}
      <div className="h-9 border-b border-gray-800/80 flex items-center px-3 gap-2 shrink-0 bg-[#0a0a0c] select-none">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-5 h-5 bg-gradient-to-br from-indigo-500 to-purple-600 rounded flex items-center justify-center shrink-0">
            <Zap size={11}/>
          </div>
          <span className="text-[11px] text-gray-300 font-semibold tracking-tight truncate">Propgatics · GenAI Ops Intelligence</span>
          <span className="text-gray-700 hidden sm:block">·</span>
          <span className="text-[10px] text-gray-600 hidden sm:block truncate">logistics-ai-assistant</span>
        </div>
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <span className="text-[9px] text-gray-600 font-mono hidden md:block">mock provider</span>
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse"/>
            <span className="text-[9px] text-gray-500">live</span>
          </div>
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Activity bar — hidden on mobile */}
        <div className="hidden md:flex w-12 bg-[#0a0a0c] border-r border-gray-800/80 flex-col items-center py-2 gap-1 shrink-0 select-none">
          {SIDE_ICONS.map(({ id, icon, tip }) => (
            <button key={id} title={tip}
              onClick={() => { if (sidePanel === id) setSideCollapsed(c => !c); else { setSidePanel(id); setSideCollapsed(false); }}}
              className={`w-9 h-9 flex items-center justify-center rounded transition-colors ${
                sidePanel === id && !sideCollapsed ? "bg-gray-700/50 text-white" : "text-gray-600 hover:text-gray-300 hover:bg-gray-800/40"
              }`}>
              {icon}
            </button>
          ))}
          <div className="mt-auto">
            <button title="Settings" className="w-9 h-9 flex items-center justify-center rounded text-gray-600 hover:text-gray-300 hover:bg-gray-800/40 transition-colors">
              <Settings size={15}/>
            </button>
          </div>
        </div>

        {/* Side panel — hidden on mobile */}
        {!sideCollapsed && (
          <div className="hidden md:flex w-56 bg-[#0f0f12] border-r border-gray-800/60 flex-col shrink-0">
            {sidePanel === "explorer" && <DocumentsPanel docs={docs} serverDocs={serverDocs} onUpload={ingestFile} uploading={uploading}/>}
            {sidePanel === "history" && <HistoryPanel history={queryHistory} onSelect={q => handleSend(q)}/>}
            {sidePanel === "stats" && <StatsPanel stats={stats}/>}
          </div>
        )}

        {/* Main editor area */}
        <div className="flex-1 flex flex-col min-w-0">
          {/* Tab bar — scrollable on mobile */}
          <div className="h-9 bg-[#0a0a0c] border-b border-gray-800/80 flex items-end shrink-0 overflow-x-auto scrollbar-none select-none">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-1.5 px-3 md:px-4 h-full text-[11px] border-r border-gray-800/60 transition-colors whitespace-nowrap ${
                  activeTab === t.id
                    ? "bg-[#0d0d0f] text-gray-200 border-t border-indigo-500 border-t-[1.5px]"
                    : "text-gray-500 hover:text-gray-300 hover:bg-gray-800/20"
                }`}>
                {t.icon}<span className="hidden sm:inline">{t.label}</span>
              </button>
            ))}
          </div>

          {/* Breadcrumb — hidden on mobile */}
          <div className="hidden sm:flex h-7 border-b border-gray-800/40 items-center px-4 gap-1 shrink-0 bg-[#0d0d0f] select-none">
            <span className="text-[10px] text-gray-600">workspace</span>
            <ChevronRight size={10} className="text-gray-700"/>
            <span className="text-[10px] text-gray-500">{activeTab}</span>
            {activeTab === "chat" && queryHistory.length > 0 && (
              <>
                <ChevronRight size={10} className="text-gray-700"/>
                <span className="text-[10px] text-gray-500 font-mono truncate max-w-[200px]">{queryHistory[queryHistory.length-1]?.q.slice(0,30)}…</span>
              </>
            )}
            <div className="ml-auto flex items-center gap-2">
              <button onClick={() => { fetchStats().then(setStats).catch(() => {}); fetchDocuments().then(setServerDocs).catch(() => {}); }} className="text-gray-600 hover:text-gray-400 transition-colors">
                <RefreshCw size={10}/>
              </button>
              {stats && <span className="text-[9px] text-gray-600 font-mono">{stats.db_rows} rows · {stats.chunk_count} chunks · {stats.queries_this_session} queries</span>}
            </div>
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0 flex flex-col">
            {activeTab === "chat" && (
              <>
                <div className="flex-1 overflow-y-auto px-6 py-4">
                  {messages.map(m => <MessageBubble key={m.id} msg={m}/>)}
                  {loading && (
                    <div className="flex gap-2.5 mb-4">
                      <div className="w-6 h-6 rounded bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shrink-0">
                        <Zap size={11}/>
                      </div>
                      <div className="bg-gray-800/50 border border-gray-700/30 rounded-lg px-4 py-3 flex items-center gap-2">
                        <Loader2 size={11} className="animate-spin text-indigo-400"/>
                        <span className="text-[11px] text-gray-500 font-mono">routing · processing…</span>
                      </div>
                    </div>
                  )}
                  <div ref={bottomRef}/>
                </div>

                {/* Suggestions — scrollable on mobile */}
                <div className="px-3 pb-2 border-t border-gray-800/40">
                  <div className="flex items-center gap-1.5 pt-2 overflow-x-auto scrollbar-none">
                    <span className="text-[9px] text-gray-600 uppercase tracking-widest shrink-0 hidden sm:block">quick:</span>
                    {suggestions.map(s => (
                      <button key={s} onClick={() => setInput(s)}
                        className="text-[10px] px-2 py-1 bg-gray-800/50 hover:bg-gray-700/60 border border-gray-700/30 hover:border-indigo-600/40 rounded text-gray-500 hover:text-gray-200 transition-all font-mono whitespace-nowrap shrink-0">
                        {s}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Input */}
                <div className="border-t border-gray-800/60 px-3 py-2 shrink-0 bg-[#0a0a0c]">
                  <div className="flex gap-2 items-end">
                    <div className="flex-1 bg-gray-800/50 border border-gray-700/50 focus-within:border-indigo-500/50 rounded px-3 py-2 transition-colors">
                      <textarea ref={textRef} value={input}
                        onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px"; }}
                        onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }}}
                        placeholder="Ask anything…"
                        rows={1}
                        className="w-full bg-transparent text-base sm:text-[12px] text-gray-200 placeholder-gray-600 outline-none resize-none font-mono leading-relaxed"/>
                    </div>
                    <button onClick={() => handleSend()} disabled={loading || !input.trim()}
                      className="w-11 h-11 sm:w-9 sm:h-9 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 rounded-lg flex items-center justify-center transition-colors shrink-0 active:scale-95 touch-manipulation">
                      {loading ? <Loader2 size={13} className="animate-spin"/> : <Send size={13}/>}
                    </button>
                  </div>
                  <p className="hidden sm:block text-[9px] text-gray-600 mt-1.5 font-mono">⏎ send · ⇧⏎ newline · drag file to upload</p>
                </div>
              </>
            )}

            {activeTab === "query" && (
              <div className="flex-1 overflow-y-auto p-6">
                <p className="text-[10px] text-gray-500 uppercase tracking-widest mb-4 font-semibold">Quick Queries</p>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    { label: "All delayed shipments", q: "Show all delayed shipments" },
                    { label: "Shipments by status", q: "Count shipments by status" },
                    { label: "Toronto routes", q: "Show all shipments to Toronto" },
                    { label: "Recent shipments", q: "Show the 10 most recent shipments" },
                    { label: "Critical delays", q: "Show all Critical Delay shipments" },
                    { label: "Worst delay routes", q: "Show worst delay routes" },
                    { label: "FedEx shipments", q: "Show all FedEx shipments" },
                    { label: "Vancouver routes", q: "Show shipments to Vancouver" },
                  ].map(({ label, q }) => (
                    <button key={label} onClick={() => handleSend(q)}
                      className="flex items-center gap-2 px-3 py-2.5 bg-gray-800/40 border border-gray-700/30 hover:border-sky-600/40 hover:bg-gray-800/60 rounded text-left transition-all group">
                      <Database size={11} className="text-sky-400 shrink-0"/>
                      <span className="text-[11px] text-gray-300 group-hover:text-white transition-colors">{label}</span>
                      <ChevronRight size={10} className="text-gray-600 ml-auto"/>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {activeTab === "analytics" && (
              <div className="flex-1 overflow-y-auto p-3 space-y-3">
                <p className="text-[10px] text-gray-500 uppercase tracking-widest font-semibold px-1 pt-1">Live Analytics</p>
                {DASH_CARDS.map(card => (
                  <ChartCard
                    key={card.id}
                    title={card.title}
                    desc={card.desc}
                    query={card.q}
                    icon={card.icon}
                    onAskInChat={(q) => { setActiveTab('chat'); setTimeout(() => handleSend(q), 50); }}
                  />
                ))}
              </div>
            )}

            {activeTab === "documents" && (
              <div className="flex-1 overflow-y-auto p-6">
                <DocumentsPanel docs={docs} serverDocs={serverDocs} onUpload={ingestFile} uploading={uploading}/>
              </div>
            )}

            {activeTab === "history" && (
              <div className="flex-1 min-h-0">
                <HistoryPanel history={queryHistory} onSelect={q => handleSend(q)}/>
              </div>
            )}

            {activeTab === "stats" && (
              <div className="flex-1 min-h-0">
                <StatsPanel stats={stats}/>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Status bar */}
      <div className="h-6 bg-indigo-700/80 border-t border-indigo-600/50 flex items-center px-3 gap-3 shrink-0 overflow-x-auto scrollbar-none select-none">
        <span className="flex items-center gap-1 text-[9px] text-indigo-200 font-mono shrink-0"><Zap size={9}/>4 agents</span>
        <span className="flex items-center gap-1 text-[9px] text-indigo-200 font-mono shrink-0"><Database size={9}/>{stats?.db_rows ?? 0} rows</span>
        <span className="hidden sm:flex items-center gap-1 text-[9px] text-indigo-200 font-mono shrink-0"><Layers size={9}/>{stats?.chunk_count ?? 0} chunks</span>
        <span className="hidden sm:flex items-center gap-1 text-[9px] text-indigo-200 font-mono shrink-0"><Activity size={9}/>{stats?.queries_this_session ?? 0} queries</span>
        <span className="ml-auto text-[9px] text-indigo-300 font-mono shrink-0 hidden md:block">{new Date().toLocaleString()}</span>
      </div>
    </div>
  );
}
