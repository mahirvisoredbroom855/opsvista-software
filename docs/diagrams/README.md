# Diagrams

Mermaid source files for OpsVista's architecture. Paste any `.mmd` file's
contents into a Mermaid renderer (e.g. the [Mermaid Live
Editor](https://mermaid.live)) to view it, or open it directly in an editor
that renders Mermaid inline (GitHub does this automatically for `.mmd` files
embedded in Markdown, but not for standalone `.mmd` files — copy the contents
into a ```mermaid fenced code block in a `.md` file if you want it to render
on GitHub itself).

- **`high-level-architecture.mmd`** — the two top-level flows: ingestion
  (Google Drive → `build_drive_index.py` → primary index + Supabase) and
  chat (Employee → Chat UI → Backend → primary index, with a fallback to
  Supabase/pgvector).
- **`chat-request-sequence.mmd`** — the full step-by-step path a single chat
  message takes, from the moment someone hits Send to the moment the answer
  (and its sources, trace panel, and audit log write) is done. Covers the
  dual-path retrieval decision (primary index vs. pgvector fallback), the
  token-budget trim, the SSE streaming events, and the best-effort audit
  logging that happens after the response is already sent.
