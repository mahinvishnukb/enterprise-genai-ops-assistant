import { useState, useRef, useEffect, useCallback } from "react";
import { sendChatMessage, uploadDocument, fetchStats, ChatResponse, StatsResponse } from "./api";
import {
  Send, Upload, FileText, Database, Brain, Loader2, CheckCircle,
  ChevronDown, ChevronUp, Zap, X, AlertCircle, BarChart2,
  ArrowUpDown, Hash, Clock, Layers,
} from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────
type Message = {
  id: number;
  role: "user" | "assistant";
  text: string;
  meta?: ChatResponse;
  error?: boolean;
  ts: number;
};
type UploadedFile = { name: string; chunks: number };
type SortDir = "asc" | "desc";

let msgId = 0;

// ─── Helpers ──────────────────────────────────────────────────────────────────
function ts() { return Date.now(); }
function fmtTime(ms: number) {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ─── Sub-components ───────────────────────────────────────────────────────────
const AGENT_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  sql_agent: { label: "SQL Agent", color: "bg-sky-950/70 text-sky-300 border-sky-700/50", icon: <Database size={9} /> },
  analytics_agent: { label: "Analytics Agent", color: "bg-emerald-950/70 text-emerald-300 border-emerald-700/50", icon: <BarChart2 size={9} /> },
  knowledge_agent: { label: "Knowledge Agent", color: "bg-violet-950/70 text-violet-300 border-violet-700/50", icon: <Brain size={9} /> },
  conversation_agent: { label: "Assistant", color: "bg-gray-800/70 text-gray-300 border-gray-600/50", icon: <Zap size={9} /> },
};

function AgentPill({ agent }: { agent: string }) {
  const meta = AGENT_META[agent] ?? AGENT_META.conversation_agent;
  return (
    <span className={`inline-flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-widest px-2.5 py-1 rounded-full border ${meta.color}`}>
      {meta.icon}{meta.label}
    </span>
  );
}

const AGENT_COLORS: Record<string, string> = {
  sql_agent: "text-sky-500",
  analytics_agent: "text-emerald-500",
  knowledge_agent: "text-violet-500",
  conversation_agent: "text-gray-400",
};

function RoutingTrace({ agent }: { agent: string }) {
  return (
    <div className="flex items-center gap-2 text-[10px] text-gray-500 mb-2 font-mono">
      <span className="text-gray-600">router</span>
      <span className="text-gray-700">→</span>
      <span className={AGENT_COLORS[agent] ?? "text-gray-400"}>{agent}</span>
      <span className="text-gray-700">→</span>
      <span className="text-green-600">done</span>
    </div>
  );
}

function MetricsGrid({ metrics }: { metrics: Record<string, string | number> }) {
  return (
    <div className="grid grid-cols-2 gap-2 mt-3">
      {Object.entries(metrics).map(([k, v]) => (
        <div key={k} className="bg-gray-900/60 border border-gray-700/30 rounded-lg px-3 py-2">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider">{k}</p>
          <p className="text-sm font-bold text-white mt-0.5">{String(v)}</p>
        </div>
      ))}
    </div>
  );
}

function MarkdownText({ text }: { text: string }) {
  const html = text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-semibold">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em class="text-gray-300 italic">$1</em>')
    .replace(/^• (.+)$/gm, '<li class="ml-3 list-disc text-gray-300">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-3 list-decimal text-gray-300">$2</li>')
    .replace(/\n\n/g, '</p><p class="mt-2">')
    .replace(/\n/g, '<br/>');
  return <p className="text-sm leading-relaxed text-gray-200" dangerouslySetInnerHTML={{ __html: html }} />;
}

function SortableTable({ rows }: { rows: Record<string, unknown>[] }) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [page, setPage] = useState(0);
  const PAGE = 8;

  if (!rows.length) return <p className="text-gray-500 text-sm italic">No rows returned.</p>;
  const cols = Object.keys(rows[0]);

  function toggleSort(col: string) {
    if (sortCol === col) setDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortCol(col); setDir("asc"); }
    setPage(0);
  }
  function setDir(d: SortDir) { setSortDir(d); }

  const sorted = [...rows].sort((a, b) => {
    if (!sortCol) return 0;
    const av = String(a[sortCol] ?? "");
    const bv = String(b[sortCol] ?? "");
    return sortDir === "asc" ? av.localeCompare(bv, undefined, { numeric: true }) : bv.localeCompare(av, undefined, { numeric: true });
  });

  const pageCount = Math.ceil(sorted.length / PAGE);
  const visible = sorted.slice(page * PAGE, (page + 1) * PAGE);

  return (
    <div className="mt-3">
      <div className="overflow-x-auto rounded-xl border border-gray-700/60 shadow-lg">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="bg-gray-800/80 border-b border-gray-700/60">
              {cols.map((c) => (
                <th
                  key={c}
                  onClick={() => toggleSort(c)}
                  className="px-4 py-2.5 text-left text-gray-400 font-semibold uppercase tracking-wider cursor-pointer hover:text-gray-200 select-none whitespace-nowrap group"
                >
                  <span className="flex items-center gap-1.5">
                    {c}
                    <ArrowUpDown size={9} className={`transition-opacity ${sortCol === c ? "opacity-100 text-sky-400" : "opacity-0 group-hover:opacity-50"}`} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/60">
            {visible.map((row, i) => (
              <tr key={i} className="hover:bg-gray-800/40 transition-colors">
                {cols.map((c) => (
                  <td key={c} className="px-4 py-2.5 text-gray-300 whitespace-nowrap font-mono text-[11px]">
                    {String(row[c] ?? "—")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pageCount > 1 && (
        <div className="flex items-center justify-between mt-2 text-xs text-gray-500">
          <span>{rows.length} total rows</span>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              className="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 transition-colors">‹</button>
            <span>{page + 1} / {pageCount}</span>
            <button onClick={() => setPage(p => Math.min(pageCount - 1, p + 1))} disabled={page === pageCount - 1}
              className="px-2 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 transition-colors">›</button>
          </div>
        </div>
      )}
    </div>
  );
}

function SQLViewer({ sql }: { sql: string }) {
  const [open, setOpen] = useState(false);
  const keywords = ["SELECT", "FROM", "WHERE", "ORDER BY", "GROUP BY", "LIMIT", "JOIN", "ON", "AND", "OR", "AS", "COUNT", "DISTINCT"];

  const highlighted = sql.replace(
    new RegExp(`\\b(${keywords.join("|")})\\b`, "g"),
    (match) => `<span class="text-sky-400 font-semibold">${match}</span>`
  ).replace(/('[^']*')/g, `<span class="text-amber-400">$1</span>`)
   .replace(/\b(\d+)\b/g, `<span class="text-emerald-400">$1</span>`);

  return (
    <div className="mt-3">
      <button onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors font-mono">
        {open ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
        {open ? "hide" : "view"} generated SQL
      </button>
      {open && (
        <pre className="mt-2 p-4 bg-gray-950 border border-gray-700/50 rounded-lg text-xs text-gray-300 overflow-x-auto leading-relaxed"
          dangerouslySetInnerHTML={{ __html: highlighted }} />
      )}
    </div>
  );
}

function SourceChips({ sources }: { sources: { doc_id: string; chunk_id: string; score: number }[] }) {
  return (
    <div className="mt-3 pt-3 border-t border-gray-700/40">
      <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 font-semibold">Retrieved chunks</p>
      <div className="flex flex-wrap gap-1.5">
        {sources.map((s) => (
          <div key={s.chunk_id} className="flex items-center gap-1.5 text-[10px] bg-gray-800 border border-gray-700/50 rounded-full px-2.5 py-1 text-gray-400">
            <FileText size={9} className="text-violet-400" />
            <span>{s.doc_id}</span>
            <span className="text-gray-600">·</span>
            <span className="text-gray-500 font-mono">{s.score.toFixed(3)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg }: { msg: Message }) {
  const isUser = msg.role === "user";
  if (isUser) {
    return (
      <div className="flex justify-end mb-6 group">
        <div className="max-w-[70%] flex flex-col items-end gap-1">
          <div className="bg-indigo-600 text-white rounded-2xl rounded-br-sm px-5 py-3 shadow-lg shadow-indigo-900/20">
            <p className="text-sm leading-relaxed">{msg.text}</p>
          </div>
          <span className="text-[10px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity">{fmtTime(msg.ts)}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start mb-6 group">
      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mr-3 mt-1 shrink-0 shadow">
        <Zap size={13} />
      </div>
      <div className="max-w-[80%] flex flex-col gap-1">
        {msg.meta && (
          <div className="flex items-center gap-2 mb-1">
            <AgentPill agent={msg.meta.agent} />
          </div>
        )}
        <div className={`rounded-2xl rounded-tl-sm px-5 py-4 shadow ${
          msg.error
            ? "bg-red-950/50 border border-red-800/50 text-red-300"
            : "bg-gray-800/70 border border-gray-700/30 text-gray-100 backdrop-blur-sm"
        }`}>
          {msg.meta?.agent === "sql_agent" && (
            <>
              <RoutingTrace agent={msg.meta.agent} />
              <p className="text-sm text-gray-300 mb-1">
                Found <span className="font-bold text-white text-base">{msg.meta.row_count}</span>{" "}
                <span className="text-gray-400">rows</span>
              </p>
              {msg.meta.rows && <SortableTable rows={msg.meta.rows} />}
              {msg.meta.sql && <SQLViewer sql={msg.meta.sql} />}
            </>
          )}
          {msg.meta?.agent === "analytics_agent" && (
            <>
              <RoutingTrace agent={msg.meta.agent} />
              {msg.text && <MarkdownText text={msg.text} />}
              {msg.meta.metrics && <MetricsGrid metrics={msg.meta.metrics} />}
              {msg.meta.rows && msg.meta.rows.length > 0 && (
                <div className="mt-3">
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-1.5 font-semibold">Underlying data</p>
                  <SortableTable rows={msg.meta.rows} />
                </div>
              )}
            </>
          )}
          {(!msg.meta || msg.meta.agent === "knowledge_agent" || msg.meta.agent === "conversation_agent") && (
            <>
              {msg.meta && <RoutingTrace agent={msg.meta.agent} />}
              <MarkdownText text={msg.text} />
              {msg.meta?.sources && msg.meta.sources.length > 0 && (
                <SourceChips sources={msg.meta.sources} />
              )}
            </>
          )}
          {msg.error && !msg.meta && <p className="text-sm text-red-300">{msg.text}</p>}
        </div>
        <span className="text-[10px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity ml-1">{fmtTime(msg.ts)}</span>
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start mb-6">
      <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center mr-3 shrink-0 shadow">
        <Zap size={13} />
      </div>
      <div className="bg-gray-800/70 border border-gray-700/30 rounded-2xl rounded-tl-sm px-5 py-4">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map(i => (
            <div key={i} className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce"
              style={{ animationDelay: `${i * 0.15}s` }} />
          ))}
          <span className="ml-2 text-xs text-gray-500 font-mono">routing · processing</span>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub }: { icon: React.ReactNode; label: string; value: string | number; sub?: string }) {
  return (
    <div className="bg-gray-800/40 border border-gray-700/30 rounded-xl p-3 flex items-start gap-3">
      <div className="text-indigo-400 mt-0.5">{icon}</div>
      <div>
        <p className="text-lg font-bold text-white leading-none">{value}</p>
        <p className="text-[10px] text-gray-400 mt-0.5">{label}</p>
        {sub && <p className="text-[10px] text-gray-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function Toast({ msg, onClose }: { msg: string; onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-3 bg-gray-800 border border-gray-600 rounded-xl px-4 py-3 shadow-xl text-sm text-gray-200 animate-in fade-in slide-in-from-bottom-4">
      <CheckCircle size={15} className="text-green-400" />
      {msg}
      <button onClick={onClose} className="text-gray-500 hover:text-gray-300 ml-1"><X size={13} /></button>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: msgId++, role: "assistant", ts: ts(),
      text: "Hello. I'm your Enterprise GenAI Operations Assistant — ask me anything about your uploaded documents or operations database. I'll route your question to the right agent automatically.",
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [stats, setStats] = useState<StatsResponse | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {});
    const interval = setInterval(() => fetchStats().then(setStats).catch(() => {}), 10000);
    return () => clearInterval(interval);
  }, []);

  async function handleSend() {
    const question = input.trim();
    if (!question || loading) return;
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setMessages(prev => [...prev, { id: msgId++, role: "user", text: question, ts: ts() }]);
    setLoading(true);
    try {
      const historySnapshot = messages.map(m => ({ role: m.role, text: m.text }));
      const result = await sendChatMessage(question, historySnapshot);
      const text = result.agent === "sql_agent"
        ? `Found ${result.row_count} rows`
        : (result.answer ?? "(no answer)");
      setMessages(prev => [...prev, { id: msgId++, role: "assistant", text, meta: result, ts: ts() }]);
    } catch (err) {
      setMessages(prev => [...prev, { id: msgId++, role: "assistant", text: `Error: ${(err as Error).message}`, error: true, ts: ts() }]);
    } finally {
      setLoading(false);
    }
  }

  const ingestFile = useCallback(async (file: File) => {
    setUploading(true);
    try {
      const res = await uploadDocument(file);
      setUploadedFiles(prev => [...prev, { name: file.name, chunks: res.chunk_count }]);
      setMessages(prev => [...prev, {
        id: msgId++, role: "assistant", ts: ts(),
        text: `Ingested "${file.name}" → ${res.chunk_count} chunks indexed in vector store. You can now query it.`,
      }]);
      setToast(`"${file.name}" ingested (${res.chunk_count} chunks)`);
      fetchStats().then(setStats).catch(() => {});
    } catch {
      setMessages(prev => [...prev, { id: msgId++, role: "assistant", text: `Upload failed for "${file.name}".`, error: true, ts: ts() }]);
    } finally {
      setUploading(false);
    }
  }, []);

  function handleFileInput(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) ingestFile(file);
    e.target.value = "";
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) ingestFile(file);
  }

  function autoResize(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
  }

  const suggestions = [
    { label: "KPI Summary", query: "Give me a KPI summary of operations" },
    { label: "Delay hotspots", query: "Which routes have the most delays?" },
    { label: "Show delayed", query: "Show all delayed shipments" },
    { label: "What can you do?", query: "What can you do?" },
  ];

  return (
    <div className="flex h-full bg-gray-950 font-sans"
      onDragOver={e => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}>

      {/* Drag overlay */}
      {dragOver && (
        <div className="fixed inset-0 z-50 bg-indigo-950/80 border-2 border-dashed border-indigo-400 flex items-center justify-center backdrop-blur-sm">
          <div className="text-center">
            <Upload size={40} className="text-indigo-300 mx-auto mb-3" />
            <p className="text-indigo-200 text-lg font-semibold">Drop to ingest document</p>
            <p className="text-indigo-400 text-sm mt-1">Supports .txt .pdf .docx .csv</p>
          </div>
        </div>
      )}

      {/* Sidebar */}
      <aside className="w-64 bg-gray-900/80 border-r border-gray-800/60 flex flex-col shrink-0 backdrop-blur-sm">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-gray-800/60">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center shadow-lg shadow-indigo-900/40">
              <Zap size={15} />
            </div>
            <div>
              <p className="text-sm font-semibold text-white tracking-tight">GenAI Ops</p>
              <p className="text-[10px] text-gray-500 font-mono">v1.0 · mock provider</p>
            </div>
          </div>
        </div>

        {/* Stats */}
        {stats && (
          <div className="px-4 py-4 border-b border-gray-800/60 space-y-2">
            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2">System</p>
            <StatCard icon={<Hash size={13} />} label="DB rows indexed" value={stats.db_rows} />
            <StatCard icon={<Layers size={13} />} label="Doc chunks" value={stats.chunk_count} />
            <StatCard icon={<BarChart2 size={13} />} label="Queries this session" value={stats.queries_this_session} />
          </div>
        )}

        {/* Upload */}
        <div className="px-4 py-4 border-b border-gray-800/60">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-3">Knowledge Base</p>
          <button onClick={() => fileRef.current?.click()} disabled={uploading}
            className="w-full flex items-center justify-center gap-2 px-3 py-2.5 bg-gray-800 hover:bg-gray-750 border border-gray-700/60 hover:border-indigo-500/50 rounded-xl text-sm text-gray-300 hover:text-white transition-all disabled:opacity-40 group">
            {uploading
              ? <Loader2 size={14} className="animate-spin text-indigo-400" />
              : <Upload size={14} className="group-hover:text-indigo-400 transition-colors" />}
            {uploading ? "Ingesting…" : "Upload Document"}
          </button>
          <p className="text-[10px] text-gray-600 text-center mt-1.5">or drag & drop anywhere</p>
          <input ref={fileRef} type="file" className="hidden" onChange={handleFileInput} accept=".txt,.pdf,.docx,.csv" />
        </div>

        {/* Uploaded files */}
        {uploadedFiles.length > 0 && (
          <div className="px-4 py-4 border-b border-gray-800/60">
            <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-2">Ingested</p>
            <div className="space-y-1.5">
              {uploadedFiles.map((f, i) => (
                <div key={i} className="flex items-start gap-2 px-2.5 py-2 bg-gray-800/50 rounded-lg border border-gray-700/30">
                  <CheckCircle size={11} className="text-green-400 mt-0.5 shrink-0" />
                  <div className="min-w-0">
                    <p className="text-xs text-gray-200 truncate font-medium">{f.name}</p>
                    <p className="text-[10px] text-gray-500 font-mono">{f.chunks} chunks</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Agent legend */}
        <div className="px-4 py-4 mt-auto">
          <p className="text-[10px] font-bold text-gray-500 uppercase tracking-widest mb-3">Active Agents</p>
          <div className="space-y-2">
            {[
              { icon: Zap, color: "text-gray-400", name: "ConversationAgent", desc: "chat · context-aware" },
              { icon: Database, color: "text-sky-400", name: "SQLAgent", desc: "NL2SQL · read-only" },
              { icon: BarChart2, color: "text-emerald-400", name: "AnalyticsAgent", desc: "trends · KPIs · insights" },
              { icon: Brain, color: "text-violet-400", name: "KnowledgeAgent", desc: "RAG · vector search" },
            ].map(({ icon: Icon, color, name, desc }) => (
              <div key={name} className="flex items-center gap-2.5 px-2.5 py-2 bg-gray-800/30 rounded-lg border border-gray-700/20">
                <div className="w-5 h-5 rounded-md bg-gray-800 flex items-center justify-center">
                  <Icon size={11} className={color} />
                </div>
                <div>
                  <p className="text-[11px] text-gray-300 font-medium font-mono">{name}</p>
                  <p className="text-[10px] text-gray-600">{desc}</p>
                </div>
                <div className="ml-auto w-1.5 h-1.5 bg-green-400 rounded-full" />
              </div>
            ))}
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="border-b border-gray-800/60 px-6 py-4 flex items-center justify-between shrink-0 bg-gray-900/40 backdrop-blur-sm">
          <div>
            <h1 className="text-sm font-semibold text-white tracking-tight">Enterprise Operations Assistant</h1>
            <p className="text-xs text-gray-500 mt-0.5">Multi-agent · RAG + NL2SQL · auto-routed</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5 text-xs text-gray-500 font-mono">
              <Clock size={11} />
              {new Date().toLocaleDateString()}
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
              <span className="text-xs text-gray-400 font-mono">online</span>
            </div>
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          {messages.map(m => <MessageBubble key={m.id} msg={m} />)}
          {loading && <TypingIndicator />}
          <div ref={bottomRef} />
        </div>

        {/* Suggestion chips — only on first load */}
        {messages.length <= 1 && (
          <div className="px-8 pb-4">
            <p className="text-[10px] text-gray-600 uppercase tracking-widest font-semibold mb-2">Try asking</p>
            <div className="flex flex-wrap gap-2">
              {suggestions.map(s => (
                <button key={s.label} onClick={() => setInput(s.query)}
                  className="text-xs px-3.5 py-1.5 bg-gray-800/60 hover:bg-gray-700/60 border border-gray-700/50 hover:border-indigo-500/50 rounded-full text-gray-400 hover:text-gray-200 transition-all font-medium">
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="border-t border-gray-800/60 px-8 py-5 shrink-0 bg-gray-900/30 backdrop-blur-sm">
          <div className="flex gap-3 items-end max-w-4xl">
            <div className="flex-1 bg-gray-800/60 border border-gray-700/50 focus-within:border-indigo-500/70 focus-within:bg-gray-800/80 rounded-2xl px-4 py-3.5 transition-all shadow-inner">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={autoResize}
                onKeyDown={e => {
                  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
                }}
                placeholder="Ask about documents or operations data…"
                rows={1}
                className="w-full bg-transparent text-sm text-gray-100 placeholder-gray-600 outline-none resize-none leading-relaxed"
              />
            </div>
            <button onClick={handleSend} disabled={loading || !input.trim()}
              className="w-10 h-10 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed rounded-xl flex items-center justify-center transition-all shadow-lg shadow-indigo-900/40 shrink-0 active:scale-95">
              {loading ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />}
            </button>
          </div>
          <p className="text-[10px] text-gray-600 mt-2 font-mono">⏎ send · ⇧⏎ newline · drag file to upload</p>
        </div>
      </main>

      {toast && <Toast msg={toast} onClose={() => setToast(null)} />}
    </div>
  );
}
