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
- **`auth-flow.mmd`** — how login actually works: signing in through
  Supabase Auth, the token that comes back, and what the backend does with
  it on every request afterward — the "logged in or not" check every route
  uses, the stricter "must be Owner/Admin" role check the dashboard uses,
  and the separate secret-token path the nightly cron job uses instead of a
  login.
- **`retrieval-decision.mmd`** — a focused decision flowchart on just the
  "does this answer use the primary index or fall back to pgvector?"
  question — the same logic as in the sequence diagram, pulled out on its
  own for explaining why a given answer took the path it did.
- **`ingestion-pipeline.mmd`** — the four stages a document goes through to
  become searchable: discover it on Drive, extract and chunk its text, embed
  each chunk into numbers, and write the result to both the primary index
  and the Supabase backup — the same pipeline whether it's triggered by the
  nightly cron job or the dashboard's "Reindex now" button.
