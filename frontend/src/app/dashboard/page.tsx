/**
 * This is the observability dashboard — an Owner/Admin-only screen
 * showing how the chatbot is actually performing: how many questions
 * were asked, how long answers took, how often the backup search had
 * to kick in, and which documents get cited most. It also has the
 * "Reindex now" button that tells the backend to rescan Google Drive
 * and rebuild the search index on demand.
 */
"use client";

import type { Session } from "@supabase/supabase-js";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Coins,
  Gauge,
  GitBranch,
  LineChart as LineChartIcon,
  Loader2,
  LogOut,
  type LucideIcon,
  RefreshCw,
  Sparkles,
  XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { supabase } from "../../lib/supabaseClient";

// ─────────────────────────────────────────────────────────────────────────
// MODULE: [OPS:FE-DASH]
//
// What it does: fetches GET /api/rag/admin/metrics and renders it as
// charts, stat tiles, and tables. The Metrics type below is kept in sync
// by hand with the backend's response shape — there's no shared schema
// between the two. ReindexButton, further down, is a separate piece
// that drives the reindex trigger/status endpoints.
// ─────────────────────────────────────────────────────────────────────────
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";
const REQUIRE_AUTH = process.env.NEXT_PUBLIC_REQUIRE_AUTH === "true";

type Summary = {
  total_queries: number;
  avg_latency_ms: number | null;
  p95_latency_ms: number | null;
  fallback_rate: number;
  avg_confidence: number | null;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
};

type TimeseriesPoint = {
  date: string;
  queries: number;
  fallback_count: number;
  tokens: number;
  avg_latency_ms: number | null;
};

type DocCitation = {
  title: string;
  department: string | null;
  citations: number;
};
type DeptCitation = { department: string; citations: number };

type RecentQuery = {
  query_id: string;
  query_text: string;
  created_at: string;
  processing_time_ms: number | null;
  used_fallback: boolean;
  retrieval_confidence: number | null;
  total_tokens: number | null;
  user_id: string | null;
};

type Metrics = {
  configured: boolean;
  message?: string;
  window_days: number;
  summary: Summary;
  timeseries: TimeseriesPoint[];
  top_documents: DocCitation[];
  top_departments: DeptCitation[];
  recent_queries: RecentQuery[];
  index_freshness: {
    total_documents: number;
    total_chunks: number;
    last_ingested_at: string | null;
  };
};

function StatTile({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: LucideIcon;
}) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__label">
        <Icon size={12} /> {label}
      </div>
      <div className="stat-tile__value">{value}</div>
      {hint && <div className="stat-tile__hint">{hint}</div>}
    </div>
  );
}

function fmtPct(n: number) {
  return `${Math.round(n * 100)}%`;
}

function fmtMs(n: number | null) {
  if (n === null || n === undefined) return "—";
  return n >= 1000 ? `${(n / 1000).toFixed(1)}s` : `${Math.round(n)}ms`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

type ReindexStatus = {
  status: "idle" | "running" | "completed" | "failed";
  started_at: string | null;
  finished_at: string | null;
  result: { chunks_discovered?: number } | null;
  error: string | null;
};

// [OPS:FE-DASH-a] ReindexButton()
//
// What it does: the "Reindex now" button. trigger() sends the POST
// request that starts a reindex, then poll() checks the status endpoint
// every 3 seconds and reschedules itself with setTimeout (not
// setInterval, so it can't send overlapping requests if a check is
// slow) as long as the status is still "running". If the backend says a
// reindex is already running (a 409 response), that's treated as
// success — it just means one is already being tracked, not an error.
//
// Called by: DashboardPage(), rendered next to the day-range toggle.
function ReindexButton({ session }: { session: Session | null }) {
  const [status, setStatus] = useState<ReindexStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  function authHeaders(): Record<string, string> {
    const token = session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  function poll() {
    fetch(`${API_BASE}/api/rag/admin/reindex/status`, {
      headers: authHeaders(),
    })
      .then((r) => r.json())
      .then((data: ReindexStatus) => {
        setStatus(data);
        if (data.status === "running") {
          pollRef.current = setTimeout(poll, 3000);
        } else {
          setBusy(false);
        }
      })
      .catch(() => setBusy(false));
  }

  async function trigger() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/rag/admin/reindex`, {
        method: "POST",
        headers: authHeaders(),
      });
      if (res.status === 401 || res.status === 403) {
        throw new Error("You need Owner/Admin access to trigger a reindex.");
      }
      if (!res.ok && res.status !== 409) {
        throw new Error(`HTTP ${res.status}`);
      }
      poll();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start reindex");
      setBusy(false);
    }
  }

  return (
    <div className="reindex-control">
      <button
        type="button"
        className="btn btn--gradient"
        onClick={trigger}
        disabled={busy}
      >
        {busy ? (
          <span className="flex items-center gap-1.5">
            <Loader2 size={14} className="animate-spin" /> Reindexing…
          </span>
        ) : (
          <span className="flex items-center gap-1.5">
            <RefreshCw size={14} /> Reindex now
          </span>
        )}
      </button>
      {error && (
        <span className="reindex-control__msg reindex-control__msg--error">
          <XCircle size={12} /> {error}
        </span>
      )}
      {!error && status?.status === "completed" && (
        <span className="reindex-control__msg reindex-control__msg--ok">
          <CheckCircle2 size={12} /> Done —{" "}
          {status.result?.chunks_discovered ?? 0} chunks discovered
        </span>
      )}
      {!error && status?.status === "failed" && (
        <span className="reindex-control__msg reindex-control__msg--error">
          <XCircle size={12} /> {status.error || "Reindex failed"}
        </span>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [days, setDays] = useState(7);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
    return () => {
      mounted = false;
    };
  }, [router]);

  // [OPS:FE-DASH-b] metrics fetch
  //
  // What it does: fetches the metrics for the currently selected day
  // window and stores them in state. Re-runs automatically whenever
  // `days` (the 7/30/90 toggle) or the session changes. When auth is
  // required, it waits until the login check has finished first, so it
  // never sends a request with a missing or stale token.
  useEffect(() => {
    if (REQUIRE_AUTH && !authChecked) return;
    setLoading(true);
    setError(null);

    const headers: Record<string, string> = {};
    if (session?.access_token)
      headers.Authorization = `Bearer ${session.access_token}`;

    fetch(`${API_BASE}/api/rag/admin/metrics?days=${days}`, { headers })
      .then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setMetrics)
      .catch((e) => setError(e?.message ?? "Failed to load metrics"))
      .finally(() => setLoading(false));
  }, [days, authChecked, session]);

  const maxDeptCitations = useMemo(
    () =>
      Math.max(1, ...(metrics?.top_departments.map((d) => d.citations) ?? [1])),
    [metrics],
  );

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
          <Sparkles size={11} /> Observability
        </span>
        <h1 className="page-hero__title">Logging Dashboard</h1>
        <p className="page-hero__subtitle">
          Real traceability into what the assistant is actually doing — query
          volume, latency, fallback activity, token usage, and what's actually
          being cited.
        </p>
      </div>

      <div className="card">
        <div
          className="card__section"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div className="note">
            {metrics?.configured === false
              ? "Supabase not configured"
              : `Last ${days} days`}
          </div>
          <div className="flex items-center gap-3">
            <div className="range-toggle">
              {[7, 30, 90].map((d) => (
                <button
                  key={d}
                  type="button"
                  className={`range-toggle__btn ${days === d ? "range-toggle__btn--active" : ""}`}
                  onClick={() => setDays(d)}
                >
                  {d}d
                </button>
              ))}
            </div>
            <ReindexButton session={session} />
            {session && (
              <button type="button" className="link-btn" onClick={signOut}>
                <LogOut size={12} /> Sign out
              </button>
            )}
          </div>
        </div>

        {loading && (
          <div className="card__section">
            <span className="pulse">Loading metrics…</span>
          </div>
        )}
        {error && (
          <div className="card__section">
            <div className="note" style={{ color: "var(--danger)" }}>
              Error: {error}
            </div>
          </div>
        )}

        {metrics?.configured && (
          <>
            <div className="card__section">
              <div className="stat-grid">
                <StatTile
                  icon={Activity}
                  label="Total Queries"
                  value={String(metrics.summary.total_queries)}
                />
                <StatTile
                  icon={Gauge}
                  label="Avg Latency"
                  value={fmtMs(metrics.summary.avg_latency_ms)}
                />
                <StatTile
                  icon={Gauge}
                  label="P95 Latency"
                  value={fmtMs(metrics.summary.p95_latency_ms)}
                />
                <StatTile
                  icon={GitBranch}
                  label="Fallback Rate"
                  value={fmtPct(metrics.summary.fallback_rate)}
                  hint="pgvector activations"
                />
                <StatTile
                  icon={BarChart3}
                  label="Avg Confidence"
                  value={
                    metrics.summary.avg_confidence !== null
                      ? metrics.summary.avg_confidence.toFixed(2)
                      : "—"
                  }
                />
                <StatTile
                  icon={Coins}
                  label="Total Tokens"
                  value={metrics.summary.total_tokens.toLocaleString()}
                  hint={`${metrics.summary.total_prompt_tokens.toLocaleString()} in · ${metrics.summary.total_completion_tokens.toLocaleString()} out`}
                />
              </div>
            </div>

            <div className="card__section">
              <div className="section-title">
                <BarChart3 size={14} style={{ marginRight: 6 }} /> Query Volume
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={metrics.timeseries}
                  margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    width={32}
                    allowDecimals={false}
                  />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Bar
                    dataKey="queries"
                    fill="var(--brand)"
                    radius={[3, 3, 0, 0]}
                    name="Queries"
                  />
                  <Bar
                    dataKey="fallback_count"
                    fill="var(--navy)"
                    radius={[3, 3, 0, 0]}
                    name="Fallback"
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>

            <div className="card__section">
              <div className="section-title">
                <LineChartIcon size={14} style={{ marginRight: 6 }} /> Latency
                &amp; Token Usage Over Time
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart
                  data={metrics.timeseries}
                  margin={{ top: 4, right: 8, left: 0, bottom: 4 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} width={40} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} />
                  <Line
                    type="monotone"
                    dataKey="avg_latency_ms"
                    stroke="var(--brand)"
                    strokeWidth={2}
                    dot={false}
                    name="Avg latency (ms)"
                  />
                  <Line
                    type="monotone"
                    dataKey="tokens"
                    stroke="var(--navy)"
                    strokeWidth={2}
                    dot={false}
                    name="Tokens"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="card__section dashboard-cols">
              <div>
                <div className="section-title">Top Cited Documents</div>
                <div className="ranked-list">
                  {metrics.top_documents.length === 0 && (
                    <div className="note">No citations yet in this window.</div>
                  )}
                  {metrics.top_documents.map((d) => (
                    <div key={d.title} className="ranked-list__row">
                      <div>
                        <div className="ranked-list__title">{d.title}</div>
                        {d.department && (
                          <span className="badge">{d.department}</span>
                        )}
                      </div>
                      <div className="ranked-list__count">{d.citations}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="section-title">By Department</div>
                <div className="dept-bars">
                  {metrics.top_departments.map((d) => (
                    <div key={d.department} className="dept-bar">
                      <div className="dept-bar__label">
                        <span>{d.department}</span>
                        <span>{d.citations}</span>
                      </div>
                      <div className="dept-bar__track">
                        <div
                          className="dept-bar__fill"
                          style={{
                            width: `${(d.citations / maxDeptCitations) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="card__section">
              <div className="section-title">
                Recent Queries
                <span className="note" style={{ marginLeft: 10 }}>
                  Index: {metrics.index_freshness.total_documents} docs ·{" "}
                  {metrics.index_freshness.total_chunks} chunks
                  {metrics.index_freshness.last_ingested_at &&
                    ` · last updated ${fmtDate(metrics.index_freshness.last_ingested_at)}`}
                </span>
              </div>
              <div className="data-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Query</th>
                      <th>Latency</th>
                      <th>Confidence</th>
                      <th>Fallback</th>
                      <th>Tokens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metrics.recent_queries.map((q) => (
                      <tr key={q.query_id}>
                        <td>{fmtDate(q.created_at)}</td>
                        <td style={{ whiteSpace: "normal", maxWidth: 320 }}>
                          {q.query_text}
                        </td>
                        <td>{fmtMs(q.processing_time_ms)}</td>
                        <td>
                          {q.retrieval_confidence !== null
                            ? q.retrieval_confidence.toFixed(2)
                            : "—"}
                        </td>
                        <td>{q.used_fallback ? "Yes" : "—"}</td>
                        <td>{q.total_tokens ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
