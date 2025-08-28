"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "../lib/supabaseClient";

type ChatResponse = {
  content: string;
  sources?: Array<Record<string, unknown>>;
  trace?: Record<string, unknown>;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  model?: string;
};
type StatusResponse = { llm?: Record<string, unknown>; retrieval?: Record<string, unknown> };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") || "http://localhost:8000";

export default function Page() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [assistant, setAssistant] = useState<ChatResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  // Auth: get session + listen for changes
  useEffect(() => {
    let mounted = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!mounted) return;
      setSession(data.session);
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

  // Fetch backend status (optional)
  useEffect(() => {
    fetch(`${API_BASE}/api/rag/chat/status`)
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  useEffect(() => {
    if (contentRef.current) contentRef.current.scrollTop = contentRef.current.scrollHeight;
  }, [assistant]);

  const statusText = useMemo(() => {
    const ok = (k?: object) => (k ? "• OK" : "• N/A");
    return `LLM ${ok(status?.llm)}   Retrieval ${ok(status?.retrieval)}`;
  }, [status]);

  async function send() {
    const message = input.trim();
    if (!message || loading) return;
    setLoading(true);
    setError(null);
    setAssistant({ content: "Thinking…", trace: { impl: "pending" }, usage: {} });

    try {
      const token = session?.access_token;
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Accept: "application/json",
      };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`${API_BASE}/api/rag/chat/complete`, {
        method: "POST",
        headers,
        body: JSON.stringify({ message, use_retrieval: true, debug: true, top_k: 4 }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ChatResponse = await res.json();
      setAssistant(data);
    } catch (e: any) {
      setError(e?.message ?? "Request failed");
      setAssistant(null);
    } finally {
      setLoading(false);
    }
  }

  async function signOut() {
    await supabase.auth.signOut();
    router.replace("/login");
  }

  if (!session) {
    // Brief placeholder while we check session (avoids flicker)
    return <div className="site-main"><div className="card"><div className="card__section">Checking session…</div></div></div>;
  }

  return (
    <div className="card">
      <div className="card__section" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="note">{statusText}</div>
        <div className="note">
          {session.user.email} · <button onClick={signOut} style={{ border: "none", background: "transparent", color: "var(--brand)", cursor: "pointer" }}>Sign out</button>
        </div>
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
          <button className="btn" onClick={send} disabled={loading || !input.trim()}>
            {loading ? "…" : "Send"}
          </button>
        </div>
        {error && <div className="note" style={{ color: "#b91c1c", marginTop: 8 }}>Error: {error}</div>}
      </div>

      <div className="card__section">
        <div className="content" ref={contentRef}>
          {assistant?.content ?? "Type a message above to begin."}
        </div>

        <details className="meta">
          <summary>Response details</summary>
          <pre>{JSON.stringify(
            { trace: assistant?.trace, usage: assistant?.usage, model: assistant?.model, sources: assistant?.sources },
            null, 2
          )}</pre>
        </details>
      </div>
    </div>
  );
}
