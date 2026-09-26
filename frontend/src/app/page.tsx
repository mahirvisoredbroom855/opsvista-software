"use client";

import type { Session } from "@supabase/supabase-js";
import {
  Check,
  Clock,
  Copy,
  Database,
  Gauge,
  GitBranch,
  LogOut,
  RefreshCw,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import remarkGfm from "remark-gfm";
import {
  detectNumericColumns,
  formatRelativeTime,
  formatTime,
  selectChartableColumns,
  type TableData,
  toNumber,
  uid,
} from "../lib/chatUtils";
import { supabase } from "../lib/supabaseClient";

type Source = {
  text: string;
  score: number;
  metadata: Record<string, unknown> & {
    table?: TableData;
    drive_file_id?: string;
  };
  source_display?: string;
};

type Trace = {
  impl?: string;
  used_fallback?: boolean;
  retrieval_confidence?: number;
  source_diversity?: number;
  fallback_reason?: string;
};

type StatusResponse = {
  llm?: Record<string, unknown>;
  retrieval?: Record<string, unknown>;
};

type IndexStatusResponse = {
  status: string;
  file_info?: { modified_epoch?: number };
};

type ChatMessage = {
  id: string;
  chatId?: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  trace?: Trace;
  model?: string;
  pending?: boolean;
  rating?: "up" | "down";
  createdAt: number;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";
// Auth is optional while no real Supabase project is wired up yet — set
// NEXT_PUBLIC_REQUIRE_AUTH=true once real auth is ready to re-enable the gate.
const REQUIRE_AUTH = process.env.NEXT_PUBLIC_REQUIRE_AUTH === "true";

const CHART_COLORS = [
  "#f59e0b",
  "#0ea5e9",
  "#10b981",
  "#8b5cf6",
  "#ef4444",
  "#6b7280",
];

const EXAMPLE_QUESTIONS = [
  "What was the Q3 net profit compared to Q2?",
  "What is the casual leave entitlement?",
  "Which spare parts are low on stock?",
  "Which orders are currently delayed?",
];

function ScoreBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
  return (
    <div className="score-bar" title={`Relevance ${pct}%`}>
      <div className="score-bar__fill" style={{ width: `${pct}%` }} />
    </div>
  );
}

function TableChart({ table }: { table: TableData }) {
  const numericMask = useMemo(() => detectNumericColumns(table), [table]);
  const labelColIdx = numericMask.findIndex((n) => !n);
  const allNumericColIdxs = numericMask
    .map((n, i) => (n ? i : -1))
    .filter((i) => i >= 0);
  const chartColIdxs = useMemo(
    () => selectChartableColumns(table, allNumericColIdxs),
    [table, allNumericColIdxs],
  );

  const canChart =
    chartColIdxs.length > 0 && table.rows.length <= 20 && table.rows.length > 0;
  if (!canChart) return null;

  const labelIdx = labelColIdx >= 0 ? labelColIdx : -1;
  const chartData = table.rows.map((row, i) => {
    const entry: Record<string, string | number> = {
      label: labelIdx >= 0 ? row[labelIdx] : `Row ${i + 1}`,
    };
    for (const ci of chartColIdxs) {
      entry[table.columns[ci]] = toNumber(row[ci]);
    }
    return entry;
  });

  return (
    <div className="table-chart">
      <ResponsiveContainer width="100%" height={180}>
        <BarChart
          data={chartData}
          margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 10 }}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={50}
          />
          <YAxis tick={{ fontSize: 10 }} width={48} />
          <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
          {chartColIdxs.length > 1 && (
            <Legend wrapperStyle={{ fontSize: 11 }} />
          )}
          {chartColIdxs.map((ci, i) => (
            <Bar
              key={ci}
              dataKey={table.columns[ci]}
              fill={CHART_COLORS[i % CHART_COLORS.length]}
              radius={[3, 3, 0, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function DataTable({ table }: { table: TableData }) {
  const previewRows = table.rows.slice(0, 8);
  return (
    <div className="data-table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {table.columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {previewRows.map((row) => (
            <tr key={row.join("|")}>
              {row.map((cell, j) => (
                <td key={`${table.columns[j]}-${cell}`}>{cell || "—"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {table.rows.length > previewRows.length && (
        <div className="data-table__more">
          +{table.rows.length - previewRows.length} more rows
        </div>
      )}
    </div>
  );
}

function SourceCard({ source }: { source: Source }) {
  const meta = source.metadata || {};
  const fileName = (meta.file_name as string) || "Unknown document";
  const department = (meta.department as string) || "General";
  const owner = (meta.owner_folder as string) || "";
  const fromDrive = meta.source === "google_drive";
  const table = meta.table;
  const driveFileId = meta.drive_file_id as string | undefined;
  const driveUrl = driveFileId
    ? `https://drive.google.com/file/d/${driveFileId}/view`
    : null;

  return (
    <div className="source-card">
      <div className="source-card__head">
        <span className="badge">{department}</span>
        {fromDrive && <span className="badge badge--drive">Google Drive</span>}
        <span className="source-card__file">{fileName}</span>
        {driveUrl && (
          <a
            className="source-card__link"
            href={driveUrl}
            target="_blank"
            rel="noreferrer"
          >
            Open ↗
          </a>
        )}
      </div>
      {owner && <div className="source-card__owner">{owner}</div>}

      {table ? (
        <>
          <TableChart table={table} />
          <DataTable table={table} />
        </>
      ) : (
        <div className="source-card__snippet">
          {source.text.slice(0, 220)}
          {source.text.length > 220 ? "…" : ""}
        </div>
      )}
      <ScoreBar score={source.score} />
    </div>
  );
}

/** Small "N docs from Department" cluster summary shown above the source list. */
function SourceClusters({ sources }: { sources: Source[] }) {
  const counts = new Map<string, number>();
  for (const s of sources) {
    const dept = (s.metadata?.department as string) || "General";
    counts.set(dept, (counts.get(dept) || 0) + 1);
  }
  return (
    <div className="clusters">
      {Array.from(counts.entries()).map(([dept, count]) => (
        <span key={dept} className="badge badge--cluster">
          {dept} · {count}
        </span>
      ))}
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      type="button"
      className="copy-btn"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        } catch {
          /* clipboard unavailable — silently ignore */
        }
      }}
    >
      {copied ? (
        <span className="flex items-center gap-1">
          <Check size={11} /> Copied
        </span>
      ) : (
        <span className="flex items-center gap-1">
          <Copy size={11} /> Copy
        </span>
      )}
    </button>
  );
}

/**
 * Retrieval-transparency panel: surfaces the dual-path trace (which index
 * answered, confidence, source diversity) that the backend has always sent
 * but the UI previously discarded. This is the "grounding inspector" piece
 * of a properly transparent RAG UI — showing *how* an answer was found, not
 * just what it cited.
 */
function TracePanel({ trace }: { trace: Trace }) {
  const confidencePct = Math.round((trace.retrieval_confidence ?? 0) * 100);
  const diversityPct = Math.round((trace.source_diversity ?? 0) * 100);
  const usedFallback = Boolean(trace.used_fallback);

  return (
    <div className="trace-panel">
      <div className="trace-panel__row">
        <GitBranch size={12} />
        <span>
          Path:{" "}
          <strong>
            {usedFallback ? "pgvector fallback" : "Enhanced index (primary)"}
          </strong>
        </span>
        {usedFallback && (
          <span className="badge badge--fallback">fallback used</span>
        )}
      </div>
      <div className="trace-panel__row">
        <Gauge size={12} />
        <span>
          Confidence: <strong>{confidencePct}%</strong>
        </span>
        <span className="trace-panel__sep">·</span>
        <span>
          Source diversity: <strong>{diversityPct}%</strong>
        </span>
      </div>
      {trace.fallback_reason && (
        <div className="trace-panel__row trace-panel__reason">
          <Database size={12} />
          <span>{trace.fallback_reason}</span>
        </div>
      )}
    </div>
  );
}

function FeedbackButtons({
  chatId,
  rating,
  onRate,
}: {
  chatId?: string;
  rating?: "up" | "down";
  onRate: (rating: "up" | "down") => void;
}) {
  if (!chatId) return null;
  return (
    <div className="feedback-btns">
      <button
        type="button"
        className={`feedback-btn ${rating === "up" ? "feedback-btn--active" : ""}`}
        onClick={() => onRate("up")}
        aria-label="Good answer"
        title="Good answer"
      >
        <ThumbsUp size={13} />
      </button>
      <button
        type="button"
        className={`feedback-btn ${rating === "down" ? "feedback-btn--active feedback-btn--down" : ""}`}
        onClick={() => onRate("down")}
        aria-label="Poor answer"
        title="Poor answer"
      >
        <ThumbsDown size={13} />
      </button>
    </div>
  );
}

export default function Page() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [indexStatus, setIndexStatus] = useState<IndexStatusResponse | null>(
    null,
  );
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!REQUIRE_AUTH) {
      setAuthChecked(true);
      return;
    }
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
      setAuthChecked(true);
      if (!data.session) router.replace("/login");
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_evt, s) => {
      setSession(s);
      if (!s) router.replace("/login");
    });
    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, [router]);

  useEffect(() => {
    fetch(`${API_BASE}/api/rag/chat/status`)
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => setStatus(null));
    fetch(`${API_BASE}/api/rag/chat/index/status`)
      .then((r) => r.json())
      .then(setIndexStatus)
      .catch(() => setIndexStatus(null));
  }, []);

  useEffect(() => {
    if (scrollRef.current)
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, []);

  const statusText = useMemo(() => {
    const ok = (k?: object) => (k ? "Online" : "Unavailable");
    return `LLM ${ok(status?.llm)} · Retrieval ${ok(status?.retrieval)}`;
  }, [status]);

  const syncedText = useMemo(() => {
    const epoch = indexStatus?.file_info?.modified_epoch;
    if (indexStatus?.status !== "operational" || !epoch) return null;
    return `Synced ${formatRelativeTime(epoch)}`;
  }, [indexStatus]);

  function applyToMessage(
    id: string,
    updater: (m: ChatMessage) => ChatMessage,
  ) {
    setMessages((prev) => prev.map((m) => (m.id === id ? updater(m) : m)));
  }

  async function rateMessage(messageId: string, rating: "up" | "down") {
    let chatId: string | undefined;
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId) return m;
        chatId = m.chatId;
        return { ...m, rating };
      }),
    );
    if (!chatId) return;
    try {
      const token = session?.access_token;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) headers.Authorization = `Bearer ${token}`;
      await fetch(`${API_BASE}/api/rag/chat/feedback`, {
        method: "POST",
        headers,
        body: JSON.stringify({ query_id: chatId, rating }),
      });
    } catch {
      /* best-effort — feedback not landing shouldn't disrupt the chat */
    }
  }

  async function sendMessage(message: string) {
    if (!message.trim() || loading) return;
    setLoading(true);
    setError(null);
    setInput("");

    const userMsg: ChatMessage = {
      id: uid(),
      role: "user",
      content: message,
      createdAt: Date.now(),
    };
    const pendingMsg: ChatMessage = {
      id: uid(),
      role: "assistant",
      content: "",
      pending: true,
      createdAt: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg, pendingMsg]);

    try {
      const token = session?.access_token;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
      };
      if (token) headers.Authorization = `Bearer ${token}`;

      const res = await fetch(`${API_BASE}/api/rag/chat/stream`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message, top_k: 4 }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let content = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const frames = buffer.split("\n\n");
        buffer = frames.pop() ?? "";

        for (const frame of frames) {
          const eventLine = frame
            .split("\n")
            .find((l) => l.startsWith("event: "));
          const dataLine = frame
            .split("\n")
            .find((l) => l.startsWith("data: "));
          if (!eventLine || !dataLine) continue;

          const eventName = eventLine.slice("event: ".length);
          const data = JSON.parse(dataLine.slice("data: ".length));

          if (eventName === "meta") {
            applyToMessage(pendingMsg.id, (m) => ({
              ...m,
              chatId: data.chat_id,
              sources: data.sources,
              trace: data.trace,
            }));
          } else if (eventName === "token") {
            content += data.content;
            applyToMessage(pendingMsg.id, (m) => ({ ...m, content }));
          } else if (eventName === "error") {
            content += `\n\n_${data.message}_`;
            applyToMessage(pendingMsg.id, (m) => ({ ...m, content }));
          } else if (eventName === "done") {
            applyToMessage(pendingMsg.id, (m) => ({
              ...m,
              model: data.model,
              pending: false,
            }));
          }
        }
      }

      applyToMessage(pendingMsg.id, (m) => ({ ...m, pending: false }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setMessages((prev) => prev.filter((m) => m.id !== pendingMsg.id));
    } finally {
      setLoading(false);
    }
  }

  function send() {
    sendMessage(input.trim());
  }

  function clearChat() {
    setMessages([]);
    setError(null);
  }

  async function signOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  if (REQUIRE_AUTH && !authChecked) {
    return (
      <div className="card">
        <div className="card__section">Checking session…</div>
      </div>
    );
  }

  return (
    <>
      <div className="page-hero">
        <span className="page-hero__eyebrow">
          <Sparkles size={11} />
          Precision Textile Industry · Internal
        </span>
        <h1 className="page-hero__title">
          Knowledge{" "}
          <span className="bg-gradient-to-r from-brand-deep via-brand to-amber-400 bg-clip-text text-transparent">
            Assistant
          </span>
        </h1>
        <p className="page-hero__subtitle">
          Ask natural-language questions over Finance, HR, Commercial,
          Maintenance, Admin, and Accounting records — answers are grounded and
          cited from source documents in Google Drive.
        </p>
      </div>
      <div className="card card--glass">
        <div className="card__section chat-topbar">
          <div className="note">
            {statusText}
            {syncedText && (
              <span
                className="sync-badge"
                title="Last time the knowledge base was rebuilt from Google Drive"
              >
                <Clock size={11} /> {syncedText}
              </span>
            )}
          </div>
          <div className="chat-topbar__right">
            {messages.length > 0 && (
              <button type="button" className="link-btn" onClick={clearChat}>
                <RefreshCw size={12} /> New conversation
              </button>
            )}
            {session && (
              <>
                <span className="note">
                  {(session.user.user_metadata?.full_name as string) ||
                    session.user.email}
                </span>
                <button type="button" className="link-btn" onClick={signOut}>
                  <LogOut size={12} /> Sign out
                </button>
              </>
            )}
          </div>
        </div>

        <div className="card__section chat-scroll" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              <p>
                Ask about finance, HR, inventory, maintenance, or commercial
                documents.
              </p>
              <div className="example-chips">
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    type="button"
                    key={q}
                    className="example-chip"
                    onClick={() => sendMessage(q)}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className={`animate-fade-in msg msg--${m.role}`}>
              <div className="msg__bubble">
                {m.pending && !m.content ? (
                  <span className="pulse">Thinking…</span>
                ) : m.role === "assistant" ? (
                  <div className="markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {m.content}
                    </ReactMarkdown>
                    {m.pending && (
                      <span className="pulse pulse--inline">▌</span>
                    )}
                  </div>
                ) : (
                  m.content
                )}
              </div>
              <div className="msg__meta">
                <span className="msg__time">{formatTime(m.createdAt)}</span>
                {m.role === "assistant" && !m.pending && (
                  <>
                    <CopyButton text={m.content} />
                    <FeedbackButtons
                      chatId={m.chatId}
                      rating={m.rating}
                      onRate={(r) => rateMessage(m.id, r)}
                    />
                  </>
                )}
              </div>
              {m.role === "assistant" && !m.pending && m.trace && (
                <TracePanel trace={m.trace} />
              )}
              {m.role === "assistant" &&
                !m.pending &&
                m.sources &&
                m.sources.length > 0 && (
                  <details className="sources">
                    <summary className="sources__summary">
                      {m.sources.length} source{m.sources.length > 1 ? "s" : ""}{" "}
                      · {m.model || "model"}
                    </summary>
                    <SourceClusters sources={m.sources} />
                    <div className="sources__list">
                      {m.sources.map((s) => (
                        <SourceCard
                          key={`${s.metadata.drive_file_id ?? s.metadata.file_name}-${s.score}`}
                          source={s}
                        />
                      ))}
                    </div>
                  </details>
                )}
            </div>
          ))}
        </div>

        <div className="card__section">
          <div className="toolbar">
            <input
              className="input"
              placeholder="Ask OpsVista…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
              disabled={loading}
              aria-label="Prompt"
            />
            <button
              type="button"
              className="btn btn--gradient"
              onClick={send}
              disabled={loading || !input.trim()}
            >
              {loading ? (
                "…"
              ) : (
                <span className="flex items-center gap-1.5">
                  Send <Send size={14} />
                </span>
              )}
            </button>
          </div>
          {error && (
            <div
              className="note"
              style={{ color: "var(--danger)", marginTop: 8 }}
            >
              Error: {error}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
