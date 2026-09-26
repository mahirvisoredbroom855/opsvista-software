"use client";

import type { Session } from "@supabase/supabase-js";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
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
}: {
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <div className="stat-tile">
      <div className="stat-tile__label">{label}</div>
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
        <span className="page-hero__eyebrow">Observability</span>
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
                  label="Total Queries"
                  value={String(metrics.summary.total_queries)}
                />
                <StatTile
                  label="Avg Latency"
                  value={fmtMs(metrics.summary.avg_latency_ms)}
                />
                <StatTile
                  label="P95 Latency"
                  value={fmtMs(metrics.summary.p95_latency_ms)}
                />
                <StatTile
                  label="Fallback Rate"
                  value={fmtPct(metrics.summary.fallback_rate)}
                  hint="pgvector activations"
                />
                <StatTile
                  label="Avg Confidence"
                  value={
                    metrics.summary.avg_confidence !== null
                      ? metrics.summary.avg_confidence.toFixed(2)
                      : "—"
                  }
                />
                <StatTile
                  label="Total Tokens"
                  value={metrics.summary.total_tokens.toLocaleString()}
                  hint={`${metrics.summary.total_prompt_tokens.toLocaleString()} in · ${metrics.summary.total_completion_tokens.toLocaleString()} out`}
                />
              </div>
            </div>

            <div className="card__section">
              <div className="section-title">Query Volume</div>
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
                Latency &amp; Token Usage Over Time
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
