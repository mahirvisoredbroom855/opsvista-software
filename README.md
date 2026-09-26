# OpsVista — RAG Knowledge Assistant

<p align="center">
  <img src="pictures/logo.png" alt="OpsVista" height="72">
</p>

<h3 align="center">Ask questions about your company's documents. Get cited, grounded answers.</h3>
<p align="center">
  Internal knowledge assistant for <strong>Precision Textile Industry LTD (PTIL)</strong>
</p>

---

## Tech Stack

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python_3.13-3776AB?style=for-the-badge&logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white">
  <img alt="Pydantic" src="https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white">
  <img alt="Uvicorn" src="https://img.shields.io/badge/Uvicorn-2C3E50?style=for-the-badge&logo=gunicorn&logoColor=white">
</p>
<p align="center">
  <img alt="Next.js" src="https://img.shields.io/badge/Next.js_15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white">
  <img alt="React" src="https://img.shields.io/badge/React_19-61DAFB?style=for-the-badge&logo=react&logoColor=black">
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white">
  <img alt="Recharts" src="https://img.shields.io/badge/Recharts-8884d8?style=for-the-badge&logo=chartdotjs&logoColor=white">
</p>
<p align="center">
  <img alt="Supabase" src="https://img.shields.io/badge/Supabase-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
  <img alt="pgvector" src="https://img.shields.io/badge/pgvector-4169E1?style=for-the-badge&logo=postgresql&logoColor=white">
</p>
<p align="center">
  <img alt="Gemini" src="https://img.shields.io/badge/Gemini_API-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white">
  <img alt="OpenAI" src="https://img.shields.io/badge/OpenAI_(optional)-412991?style=for-the-badge&logo=openai&logoColor=white">
  <img alt="Google Drive" src="https://img.shields.io/badge/Google_Drive-4285F4?style=for-the-badge&logo=googledrive&logoColor=white">
</p>
<p align="center">
  <img alt="Pytest" src="https://img.shields.io/badge/Pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white">
  <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub_Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white">
  <img alt="Render" src="https://img.shields.io/badge/Render-46E3B7?style=for-the-badge&logo=render&logoColor=white">
  <img alt="Vercel" src="https://img.shields.io/badge/Vercel-000000?style=for-the-badge&logo=vercel&logoColor=white">
</p>

| Category | What's used |
|---|---|
| **Backend runtime** | Python 3.13, FastAPI, Uvicorn, Pydantic v2, `slowapi` (rate limiting) |
| **Frontend** | Next.js 15 (App Router), React 19, TypeScript, custom CSS (no Tailwind, despite it being scaffolded), `recharts`, `react-markdown` |
| **Database, Auth & Vector Store** | Supabase — managed Postgres, Auth (JWT), Row Level Security, `pgvector` extension |
| **LLM & Embeddings** | Google Gemini (`gemini-flash-lite-latest` generation, `gemini-embedding-001` embeddings) — primary; OpenAI supported as an alternate provider |
| **Document ingestion** | Google Drive API v3, `pypdf`, `python-docx`, `pandas`/`openpyxl` |
| **Testing** | `pytest`, `pytest-asyncio`, `pytest-mock` — 27 tests covering the real ingestion/retrieval/quality-gate pipeline |
| **Hosting (target)** | Render (backend), Vercel (frontend) |

---

## What is OpsVista?

OpsVista is an internal chat assistant that answers questions about PTIL's own documents — finance records, HR policies, commercial orders, maintenance logs, admin procedures — instead of employees having to dig through Google Drive folders themselves. Every answer comes with **citations** back to the real source document, so you can verify it yourself.

## How it works (the simple version)

1. Company documents (Excel sheets, Word docs, PDFs, policies) live in Google Drive, organized by department.
2. A background process reads those documents, breaks them into chunks, and converts each chunk into a vector embedding — a numeric representation of its meaning.
3. When someone asks a question, the system embeds the question the same way and finds the most semantically similar chunks.
4. Those chunks get handed to an LLM (Gemini), which writes a plain-English answer **using only that retrieved context** — and the original chunks are shown back to the user as citations.
5. If the primary search comes back empty or low-confidence, a second independent search (Postgres/pgvector) gets a chance to find something — this is the "dual-path" part of the design.

<p align="center">
  <img src="pictures/High-Level%20System%20Architecture%20(E2E).png" alt="High-Level Architecture" width="88%">
</p>

## API at a glance

| Method | Endpoint | Purpose | Auth |
|---|---|---|---|
| `GET` | `/api/status` | Overall app health, no external calls | Public |
| `GET` | `/api/rag/chat/status` | LLM + retrieval provider status | Public |
| `GET` | `/api/rag/chat/index/status` | Index metadata (size, doc count) | Public |
| `POST` | `/api/rag/chat/complete` | Ask a question, get a cited answer (single JSON response) | Any signed-in user |
| `POST` | `/api/rag/chat/stream` | Same pipeline, streamed as Server-Sent Events | Any signed-in user |
| `GET` | `/api/rag/chat/_retrieve` | Debug: raw retrieval results, no LLM call | Any signed-in user |
| `GET` | `/api/rag/admin/metrics` | Observability dashboard data | **Owner/Admin only** |
| `POST` | `/api/rag/admin/reindex` | Trigger a full Drive re-scan + re-embed | **Owner/Admin only** |
| `GET` | `/api/rag/admin/reindex/status` | Poll reindex progress | **Owner/Admin only** |

Interactive OpenAPI docs are always available at `/docs` on a running backend.

---

# Technical Deep Dive

Everything below assumes the simple version above and goes further into how it's actually built, why specific decisions were made, and how to run/deploy it yourself.

## Dual-Path Retrieval — in detail

The primary retrieval path is an **in-memory JSON index** (`enhanced_index.json`) — every chunk and its embedding vector, loaded into memory for brute-force cosine similarity search. At this corpus size (hundreds of chunks), this is genuinely faster and more accurate than an approximate-nearest-neighbor index would be.

The fallback path is **Postgres + `pgvector`**, hosted on Supabase. It activates not just when the primary path returns literally nothing, but when its top confidence score falls below a configurable quality threshold (`RAG_QUALITY_THRESHOLD`, default `0.5`) — a genuine quality gate, not just an empty-results check.

<p align="center">
  <img src="pictures/Retrieval%20Decision%20Flow%20(Strict).png" alt="Retrieval Decision Flow" width="70%">
</p>

> **Note on this diagram:** it depicts the original binary "has hits?" design. The real implementation (`retrieve_with_trace()` in `chat.py`) is a superset of this — it adds confidence-threshold and source-diversity scoring on top of the same fallback structure shown here.

Every response carries a `trace` object showing exactly what happened:

```json
{
  "impl": "enhanced_index",
  "retrieval_confidence": 0.83,
  "source_diversity": 0.75,
  "used_fallback": false
}
```

### Full request sequence

<p align="center">
  <img src="pictures/Chat%20Request%20Sequence%20(Alt%20paths%20shown).png" alt="Chat Request Sequence" width="90%">
</p>

> The fallback box in this diagram (`IntegratedSearchManager`) is drawn from an earlier design — the real fallback implementation is `pgvector_store.py`, and the primary LLM provider is Gemini, not OpenAI (OpenAI remains supported as an alternate). The request/response shape and control flow shown are otherwise accurate.

### Response shape

```json
{
  "chat_id": "e0225265-...",
  "content": "### Summary\nAccording to the Leave and Attendance Policy...",
  "model": "gemini-flash-lite-latest",
  "sources": [
    {
      "text": "Casual Leave: 10 days, requires 1 day advance notice...",
      "score": 0.78,
      "metadata": {
        "file_name": "Leave_and_Attendance_Policy.md",
        "department": "HR",
        "source": "google_drive",
        "drive_file_id": "1abc...",
        "table": null
      }
    }
  ],
  "usage": { "prompt_tokens": 696, "completion_tokens": 126, "total_tokens": 822 },
  "trace": { "impl": "enhanced_index", "retrieval_confidence": 0.78, "used_fallback": false },
  "warnings": []
}
```

<p align="center">
  <img src="pictures/Response%20Assembly%20(What%20the%20API%20returns).png" alt="Response Assembly" width="80%">
</p>

`warnings[]` is populated when: no documents were found, the fallback path was used, the fallback was attempted but also came up empty, or the retrieved context had to be truncated to fit the token budget (`MAX_CONTEXT_TOKENS`, default `6000`).

### Streaming (`/api/rag/chat/stream`)

Retrieval works exactly like `/complete` — same dual-path logic, same quality gate — but generation is streamed back as Server-Sent Events instead of one blocking response, so the answer renders token-by-token in the UI:

| Event | Payload | When |
|---|---|---|
| `meta` | `chat_id`, `sources`, `trace`, `warnings`, `created` | Immediately after retrieval finishes, before generation starts |
| `token` | `content` (a text fragment) | Once per chunk the LLM provider streams back |
| `warning` | `message` | If context had to be truncated mid-generation |
| `error` | `message` | If generation fails after retrieval succeeded |
| `done` | `chat_id`, `model`, `usage`, `processing_time_ms` | Once the stream ends |

Both Gemini and OpenAI backends implement native token streaming (`generate_content_stream` / `chat.completions.create(stream=True)`) under `llm_client.py`. Since streamed usage accounting isn't consistently reported by either provider mid-stream, `usage` in the `done` event is estimated with the same 4-chars-per-token heuristic used for the context token budget — good enough for the audit log, not billing-grade precision. The same `fact_query`/`bridge_query_citation` audit write happens after the stream completes, identical to `/complete`.

### Excel/table-aware citations

Unlike flat text extraction, spreadsheet-derived chunks preserve their actual rows and columns in `metadata.table`. The frontend uses this to render a real data table **and** an auto-generated bar chart per citation — with a magnitude filter that drops incompatible-scale columns (e.g. a per-row amount vs. a cumulative running balance) so the chart doesn't render one series invisible next to the other.

## Data Model

<p align="center">
  <img src="pictures/Data%20Shape%20(ER)%20for%20Enhanced%20Index%20+%20Metadata.png" alt="Data Shape" width="68%">
</p>

> This diagram shows the conceptual document → chunk → embedding relationship correctly, but predates two tables that now exist for real (`fact_query`, `bridge_query_citation` — the audit log) and includes a generic key/value `METADATA` table that was never implemented (metadata lives as JSONB directly on `fact_chunk`). **[`backend/sql/schema.sql`](backend/sql/schema.sql) is the authoritative, executable schema** — five tables, real RLS policies, and the `match_chunks()` pgvector search function.

| Table | Purpose |
|---|---|
| `dim_document` | One row per source file (Drive or local), department, classification |
| `fact_chunk` | Text chunks, ordinal position, full metadata (JSONB) |
| `fact_embedding` | The actual `vector(1536)` embeddings, keyed to a chunk |
| `fact_query` | Audit log: every question asked, confidence, latency, tokens, fallback flag |
| `bridge_query_citation` | Which chunks were cited for which query, ranked |

### Why 1536 dimensions, not Gemini's native 3072?

`pgvector`'s `ivfflat`/`hnsw` indexes cap out at 2000 dimensions. Gemini's embedding model supports requesting a smaller output directly (Matryoshka representation learning) via `output_dimensionality=1536` — so the same vectors work for both the JSON index and an indexable Postgres column, at the cost of a small amount of embedding fidelity.

### Why is there no ANN index on `fact_embedding` right now?

`ivfflat` needs roughly `rows / 1000` clusters to behave well. At a few hundred rows, that rounds to ~0–1 — creating the index actually made retrieval *worse* in testing (found the wrong document, returned duplicates) because each cluster ended up with ~1 vector in it. Exact search is both more accurate and fast enough below roughly 1,000–10,000 rows. The threshold for adding it back is documented directly in `schema.sql`.

---

## Repository Structure

```
opsvista-software/
├── backend/
│   ├── app/
│   │   ├── main.py                          # FastAPI entrypoint, startup hydration, rate limiter wiring
│   │   ├── core/
│   │   │   ├── config.py                    # Pydantic Settings (dev-safe defaults)
│   │   │   ├── auth_deps.py                 # get_current_user / require_roles (RBAC)
│   │   │   ├── supabase_jwt.py              # Token verification via Supabase Auth API
│   │   │   └── rate_limit.py                # Shared slowapi Limiter instance
│   │   └── features/rag_chatbot/
│   │       ├── api/
│   │       │   ├── chat.py                  # /api/rag/chat/* — retrieval, quality gate, generation
│   │       │   ├── admin_metrics.py         # /api/rag/admin/metrics
│   │       │   └── discovery.py             # /api/rag/admin/reindex(/status)
│   │       ├── llm/
│   │       │   ├── llm_client.py            # Provider-agnostic (Gemini/OpenAI) LLM wrapper
│   │       │   └── prompt_engineering.py    # System prompt + adaptive length policy
│   │       ├── vector/
│   │       │   ├── persisted_inmemory_search.py  # Primary JSON index + shared embed_texts()
│   │       │   ├── pgvector_store.py             # Fallback search, dual-write, audit logging, hydration
│   │       │   └── google_drive_service.py       # Drive API client (service account)
│   │       └── ingestion_common.py          # Shared chunking/extraction (PDF/DOCX/XLSX/TXT/MD)
│   ├── build_local_index.py                 # Build index from a local folder (no Drive/API key needed)
│   ├── build_drive_index.py                 # Build index from real Google Drive
│   ├── sql/schema.sql                        # Full Supabase schema, RLS, match_chunks() RPC
│   ├── tests/                                # 27 pytest tests, mock embeddings, no network calls
│   └── seed_docs/                            # Realistic dummy PTIL documents (Excel/Word/PDF/MD)
│
├── frontend/src/app/
│   ├── page.tsx                              # Chat UI — conversation, citations, charts
│   ├── login/page.tsx                        # Sign in / sign up (with name + email confirmation)
│   ├── dashboard/page.tsx                    # Observability dashboard (Owner/Admin)
│   └── globals.css                           # All styling — no Tailwind in actual use
│
└── pictures/                                 # Architecture diagrams referenced throughout this file
```

---

## Getting Started

### Prerequisites

- Python ≥ 3.11
- Node.js ≥ 18
- A Supabase project (free tier is fine) with the `vector` extension enabled
- A Gemini API key ([aistudio.google.com/apikey](https://aistudio.google.com/apikey), free tier available) — or an OpenAI key as an alternative
- *(Optional, for real Drive ingestion)* a Google Cloud service account with Drive API access

### 1. Clone and install

```bash
git clone https://github.com/mahirvisoredbroom855/opsvista-software.git
cd opsvista-software

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

### 2. Configure environment

Copy `.env.example` to `.env` at the repo root and fill in:

```bash
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...        # bypasses RLS — used by ingestion & audit logging

GEMINI_API_KEY=...
GEMINI_MODEL=gemini-flash-lite-latest
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
GEMINI_EMBEDDING_DIM=1536             # must stay ≤2000 for pgvector indexing

USE_MOCK_EMBEDDINGS=false             # true = deterministic hash vectors, zero cost/API calls
GOOGLE_DRIVE_CREDENTIALS_PATH=backend/credentials/google_credentials.json
CORS_ALLOWED_ORIGINS=http://localhost:3000
```

Then run `backend/sql/schema.sql` once in your Supabase project's SQL Editor.

Copy `frontend/.env.local.example` (or create `frontend/.env.local`):

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_REQUIRE_AUTH=true
```

### 3. Build the index

No Google Drive access yet? Use the local seed documents:

```bash
cd backend
python build_local_index.py --reset
```

Have a real Drive service account set up and folders shared with it? See the step-by-step in this file's [Google Drive Setup](#google-drive-setup) section below, then:

```bash
python build_drive_index.py --reset
```

Either script dual-writes into Supabase automatically — no separate step needed.

### 4. Run it

```bash
# Terminal 1 — backend
cd backend && uvicorn app.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
```

Visit `http://localhost:3000`, sign up (or sign in), and start asking questions.

---

## Google Drive Setup

1. **Google Cloud Console** → new project → enable the **Google Drive API**.
2. **APIs & Services → Credentials** → Create Credentials → **Service Account** → create a key (JSON) → save it as `backend/credentials/google_credentials.json` (already gitignored).
3. In Google Drive, create one parent folder containing your department subfolders, and **share only that parent folder** with the service account's email (Viewer access) — permissions cascade to everything inside.
4. Upload documents into the matching department folders. Supported: Google Docs, `.pdf`, `.docx`, `.xlsx`, `.txt`, `.md`.
5. Run `python build_drive_index.py --reset` (or trigger `POST /api/rag/admin/reindex` from a signed-in Owner/Admin account).

---

## Refreshing the Index

| Method | Command / Endpoint | Notes |
|---|---|---|
| CLI, local docs | `python backend/build_local_index.py --reset` | No Drive/service-account needed |
| CLI, real Drive | `python backend/build_drive_index.py --reset` | Full rescan + re-embed + dual-write |
| API, admin-triggered | `POST /api/rag/admin/reindex` | Runs in background; requires Owner/Admin role; rate-limited to 3/min |

A timestamped backup of the previous index is kept automatically (`backend/app/features/rag_chatbot/vector/backups/`, last 5 retained) before every reset.

**On startup**, if `enhanced_index.json` is missing locally (e.g. after a redeploy on a host with ephemeral disk, like Render's free tier), the app automatically rehydrates it from Supabase — the same chunks and embeddings already dual-written there — rather than booting with an empty index.

---

## Observability & the Dashboard

<p align="center">
  <img src="pictures/Health%20%26%20Diagnostics%20(Cheap%20Observability).png" alt="Health & Diagnostics" width="70%">
</p>

Every chat request writes a row to `fact_query` (confidence, latency, tokens, fallback flag) and `bridge_query_citation` (which chunks were cited, ranked). This is real, queryable data — not just log lines.

Three ways to look at it:
1. **The dashboard** — `/dashboard` in the frontend (Owner/Admin only): query volume, latency (avg/p95), fallback rate, token usage, top cited documents/departments, recent query log.
2. **Supabase Studio** — Table Editor on `fact_query` / `bridge_query_citation` for raw data.
3. **Backend logs** — `tail -f` wherever you redirect uvicorn's output; on Render, its built-in log viewer shows the same thing automatically.

---

## Security

- **Auth**: Supabase Auth (email/password), JWTs verified server-side against Supabase's own Auth API (not a locally-held signing secret — robust across Supabase's key-format changes).
- **RBAC**: `require_roles(["Owner", "Admin"])` gates the admin dashboard and reindex trigger. Regular chat access requires only a valid session — any signed-in employee can ask questions. Grant a role via:
  ```python
  supabase.auth.admin.update_user_by_id(user_id, {"app_metadata": {"role": "Owner"}})
  ```
- **Row Level Security**: enabled on all 5 tables. The knowledge corpus (`dim_document`/`fact_chunk`/`fact_embedding`) is readable by any authenticated user, writable only via the service-role key (ingestion pipeline). Audit tables are scoped so a user can only ever see their own query history once fully wired to `auth.uid()`.
- **Rate limiting**: per-IP via `slowapi` — 20/min on chat, 60/min on metrics, 3/min on reindex, 120/min global default.
- **Secrets**: service-role keys, JWT secrets, and Drive credentials are never committed — see `.gitignore`.

---

## Testing

```bash
cd backend
pip install -r requirements-test.txt
pytest
```

27 tests, mock embeddings throughout (no network calls, no API cost), covering:
- `ingestion_common.py` — chunking, PDF/DOCX/XLSX extraction against real generated fixtures
- `persisted_inmemory_search.py` — ingest/search/persist round trips
- `chat.py` — the quality-gate logic (`_retrieval_confidence`, `_source_diversity`, `_enforce_token_budget`), and `retrieve_with_trace()`'s dual-path branching with the retrieval functions mocked out
- `pgvector_store.py` — config-detection logic (the real Supabase-dependent paths were verified manually against the live project rather than mocked, since faking the whole PostgREST surface would test the mock, not the code)

---

## Deployment

<p align="center">
  <img src="pictures/Infrastructure%20Runtime%20Topology.png" alt="Infrastructure Topology" width="80%">
</p>

> Diagram shows "OpenAI API" — Gemini is now the primary provider (OpenAI remains supported as an alternate). Everything else matches: Vercel → Render/Uvicorn → FastAPI → Chat Router → Supabase / LLM provider / Google Drive / local index file.

### Backend → Render

A [`render.yaml`](render.yaml) Blueprint is included at the repo root — in the Render dashboard, **New → Blueprint**, point it at this repo, and it pre-fills the service below (you still need to fill in the `sync: false` secrets yourself in the dashboard, since Render never reads secret values from the repo).

- **Build command**: `pip install -r requirements.txt` (repo root, not `backend/`, since that's where `requirements.txt` lives)
- **Start command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health check path**: `/api/status`
- Set every variable from your `.env` as a Render secret (never commit `.env` to the repo)
- Google Drive credentials aren't in git (see `.gitignore`) — if you want the admin-triggered reindex to work in production, upload `google_credentials.json` via Render's **Secret Files** feature at the path `GOOGLE_DRIVE_CREDENTIALS_PATH` points to. Without it, chat still works (the index hydrates from Supabase on boot); only *triggering a fresh Drive scan* needs it.

### Frontend → Vercel

- Root directory: `frontend/`
- Framework preset: Next.js (auto-detected)
- Set the `NEXT_PUBLIC_*` variables, pointing `NEXT_PUBLIC_API_BASE_URL` at your Render backend URL

### Post-deploy checklist

- [ ] `CORS_ALLOWED_ORIGINS` includes your real Vercel domain
- [ ] Supabase Auth → URL Configuration → Site URL points at your Vercel domain (needed for email-confirmation links to redirect correctly)
- [ ] `GET /api/status` returns `200` from the deployed backend
- [ ] Sign up, confirm email, sign in, ask a question, confirm citations render

---

## Troubleshooting

**"Enhanced index not found" / empty results**
Run `python backend/build_local_index.py --reset` (or `build_drive_index.py` if using real Drive). On a redeploy, check the startup logs — it should say it rehydrated from Supabase automatically; if not, verify `SUPABASE_SERVICE_ROLE_KEY` is set on the host.

**"Invalid or expired Supabase token" on every request**
Confirm `SUPABASE_URL`/`SUPABASE_ANON_KEY` match between frontend and backend, and that the frontend is actually sending an `Authorization: Bearer <token>` header (check Network tab).

**403 on `/api/rag/admin/*`**
That's RBAC working as intended — the signed-in user doesn't have `Owner` or `Admin` in their `app_metadata.role`. Grant it via the Supabase Admin API (see [Security](#security)).

**429 Too Many Requests**
Rate limiting working as intended. Wait a minute, or adjust the limits in the relevant `@limiter.limit(...)` decorator if they're genuinely too strict for your usage.

**Gemini embedding dimension mismatch after changing `GEMINI_EMBEDDING_DIM`**
The `fact_embedding.embedding` column is a fixed-width `vector(1536)`. Changing the dimension requires dropping and recreating that column (or the whole table) and rebuilding the index from scratch.

---

## License

**Proprietary Software** — © 2026 Precision Textile Industry LTD. All rights reserved. Access restricted to authorized PTIL personnel and approved contractors under confidentiality agreements.

<div align="center">

**Built for Precision Textile Industry LTD**

</div>
