# PTIL Frontend (Next.js + Supabase + RAG Chat)

A minimal, production-ready starter to connect your existing backend (FastAPI + RAG + Supabase) to a modern Next.js 14 App Router UI and deploy on Vercel.

## What’s included
- **Auth**: Supabase Auth UI (magic link / providers) and session management
- **Chat**: RAG chatbot UI with streaming via a Next.js proxy (`/api/chat`)
- **Finance**: Simple finance summary powered by Supabase table `finance_summary`
- **Tasks**: List/create tasks in Supabase `tasks` (RLS-aware)
- **Styling**: TailwindCSS

---

## Quick start

1) **Create env file**

Copy `.env.example` to `.env.local` and fill values:
```bash
cp .env.example .env.local
```

**Required:**
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `API_BASE_URL` (your FastAPI base url, e.g. `http://localhost:8000` or your hosted URL)

2) **Install & run**

```bash
# in this folder
pnpm install   # or npm i / yarn
pnpm dev       # or npm run dev / yarn dev
```

3) **Sign-in**

Open `http://localhost:3000`. If not signed in, you’ll see Supabase Auth UI. After sign-in you’ll get:
- **Chat**: Type to stream answers from FastAPI via `/api/chat`
- **Finance**: Summary cards (reads from `finance_summary`)
- **Tasks**: Your assigned tasks (reads & inserts into `tasks`)

---

## Backend expectations

- **FastAPI** exposes a chat endpoint that streams **text/event-stream**:
  - **POST** `${API_BASE_URL}/chat/stream` with JSON body `{ "query": string, "history": Array }`
  - Returns `text/event-stream` chunks as `data: <text>\n\n`
  - Accepts `Authorization: Bearer <supabase_jwt>` (optional)

- **Supabase** RLS:
  - `finance_summary` readable for authenticated
  - `tasks` selectable by `assignee_id = auth.uid()` and insertable with `assigner_id = auth.uid()`

Adjust policies as needed.

---

## Deployment (Vercel)

1) Push this project to GitHub (private or public).
2) In Vercel:
   - Create new project -> import from your repo.
   - Set Environment Variables in Vercel:
     - `NEXT_PUBLIC_SUPABASE_URL`
     - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
     - `API_BASE_URL` (your FastAPI host; if the FastAPI is elsewhere like Railway/Fly.io/Render)
3) Deploy.

> **Note:** Long-running workers (Celery) and Python backend should be hosted outside Vercel (e.g., Railway/Fly.io/Render). This app talks to them via `API_BASE_URL`.

---

## Optional enhancements
- Replace the proxy with direct SSE if your CORS allows.
- Add charts for finance (`recharts`) and nicer UI (e.g. shadcn/ui).
- Add optimistic updates and server actions for tasks.
