'use client';

import { useEffect, useRef, useState } from 'react';
import { createClient } from '@/lib/supabaseClient';

type ChatMessage = { role: 'user' | 'assistant', content: string };

export default function Chat() {
  const supabase = createClient();
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loading, setLoading] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg: ChatMessage = { role: 'user', content: input.trim() };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setLoading(true);

    try {
      // Include Supabase access token for backend auth (Bearer)
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;

      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          ...(token ? { 'authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          query: userMsg.content,
          history: messages, // send minimal history; adjust shape to match FastAPI
        }),
      });

      if (!res.ok || !res.body) {
        const text = await res.text();
        throw new Error(text || 'Request failed');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantChunk = '';

      // Parse text/event-stream or raw chunks
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        // If it's SSE "data: ...\n\n", extract the payload lines
        for (const line of chunk.split('\n')) {
          const trimmed = line.trim();
          if (trimmed.startsWith('data:')) {
            assistantChunk += trimmed.slice(5).trim() + ' ';
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy[copy.length - 1];
              // ensure we only add one assistant message that we update
              if (!last || last.role !== 'assistant') {
                copy.push({ role: 'assistant', content: '' });
              }
              copy[copy.length - 1] = {
                role: 'assistant',
                content: assistantChunk,
              };
              return copy;
            });
          } else if (trimmed && !trimmed.startsWith('event:') && !trimmed.startsWith('id:')) {
            // Fallback: accumulate plain text
            assistantChunk += trimmed + ' ';
            setMessages((prev) => {
              const copy = [...prev];
              const last = copy[copy.length - 1];
              if (!last || last.role !== 'assistant') {
                copy.push({ role: 'assistant', content: '' });
              }
              copy[copy.length - 1] = {
                role: 'assistant',
                content: assistantChunk,
              };
              return copy;
            });
          }
        }
      }
    } catch (err: any) {
      setMessages((m) => [...m, { role: 'assistant', content: '⚠️ ' + (err?.message || 'Error') }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-[450px] flex-col">
      <div ref={listRef} className="flex-1 overflow-auto rounded-xl border bg-neutral-50 p-3">
        {messages.length === 0 && (
          <div className="text-sm text-neutral-500">Ask about revenue targets, LC processing, customers, etc.</div>
        )}
        <div className="space-y-2">
          {messages.map((m, i) => (
            <div key={i} className="whitespace-pre-wrap">
              <span className={m.role === 'user' ? 'font-semibold text-blue-600' : 'font-semibold text-emerald-600'}>
                {m.role === 'user' ? 'You: ' : 'Assistant: '}
              </span>
              <span>{m.content}</span>
            </div>
          ))}
        </div>
      </div>
      <form onSubmit={onSubmit} className="mt-3 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your question…"
          className="flex-1 rounded-xl border bg-white px-3 py-2 outline-none focus:ring-2 focus:ring-blue-500"
        />
        <button
          disabled={loading}
          className="rounded-xl bg-blue-600 px-4 py-2 text-white disabled:opacity-50"
        >
          {loading ? 'Thinking…' : 'Send'}
        </button>
      </form>
    </div>
  );
}
