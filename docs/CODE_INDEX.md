# OpsVista Code Index

Master lookup for the `[OPS:MODULE-###]` tags scattered through this
codebase on branch `docs/codebase-annotations`. Each tag marks a block
comment that explains what that piece of code does, which external API it
calls, which other tagged pieces call it or are called by it, what breaks
if it's misconfigured, and where else to look for more context.

**How to use this file:** if you're preparing a presentation, a handout, or
answering "where does X happen" out loud, find the tag here, jump to
`file:line`, and read the full comment block in place — this file only
gives a one-line pointer, the real explanation lives with the code.

Line numbers are accurate as of the last commit on this branch that
touched each file; a later edit can drift them slightly — if a line number
looks off, search the file for the tag string instead (`grep -n
"OPS:CHAT-010" backend/app/features/rag_chatbot/api/chat.py`).

---

## CHAT — core request path (`backend/app/features/rag_chatbot/api/chat.py`)

The single most important module in the system: retrieval orchestration,
generation, and the HTTP surface (`/complete`, `/stream`, `/feedback`,
`/status`, `/index/status`, `/_retrieve`).

| Tag | What | Location |
|---|---|---|
| `CHAT` | Module overview — retrieval → generation → audit pipeline | [chat.py:4](../backend/app/features/rag_chatbot/api/chat.py#L4) |
| `CHAT-001` | `ChatRequest` — POST /complete and /stream body shape | [chat.py:47](../backend/app/features/rag_chatbot/api/chat.py#L47) |
| `CHAT-002` | `FeedbackRequest` — POST /feedback body shape | [chat.py:64](../backend/app/features/rag_chatbot/api/chat.py#L64) |
| `CHAT-004` | `ChatResponse` — POST /complete response shape | [chat.py:87](../backend/app/features/rag_chatbot/api/chat.py#L87) |
| `CHAT-005` | `_norm_one()` — normalizes primary/fallback results to one shape | [chat.py:125](../backend/app/features/rag_chatbot/api/chat.py#L125) |
| `CHAT-006` | `_get_enhanced_index()` — loads the primary in-memory index | [chat.py:213](../backend/app/features/rag_chatbot/api/chat.py#L213) |
| `CHAT-007` | `_enhanced_retrieve()` — the PRIMARY retrieval path | [chat.py:265](../backend/app/features/rag_chatbot/api/chat.py#L265) |
| `CHAT-008` | `_pgvector_retrieve()` — the FALLBACK retrieval path | [chat.py:304](../backend/app/features/rag_chatbot/api/chat.py#L304) |
| `CHAT-009` | Quality-gate: `RAG_QUALITY_THRESHOLD`, confidence, source diversity | [chat.py:348](../backend/app/features/rag_chatbot/api/chat.py#L348) |
| `CHAT-010` | `retrieve_with_trace()` — THE dual-path retrieval entrypoint | [chat.py:393](../backend/app/features/rag_chatbot/api/chat.py#L393) |
| `CHAT-011` | `GET /_retrieve` — retrieval-only debug endpoint | [chat.py:462](../backend/app/features/rag_chatbot/api/chat.py#L462) |
| `CHAT-012` | `_render_sources()` — shapes docs into frontend citation objects | [chat.py:490](../backend/app/features/rag_chatbot/api/chat.py#L490) |
| `CHAT-013` | `_build_context_texts()` — shapes docs for the LLM prompt | [chat.py:496](../backend/app/features/rag_chatbot/api/chat.py#L496) |
| `CHAT-014` | Token budget — `CHARS_PER_TOKEN_ESTIMATE`, `_enforce_token_budget()` | [chat.py:541](../backend/app/features/rag_chatbot/api/chat.py#L541) |
| `CHAT-015` | `POST /complete` — non-streaming chat endpoint, full pipeline | [chat.py:413](../backend/app/features/rag_chatbot/api/chat.py#L413) |
| `CHAT-019` | `_sse_event()` — formats one SSE wire frame | [chat.py:779](../backend/app/features/rag_chatbot/api/chat.py#L779) |
| `CHAT-020` | `POST /stream` — streaming chat endpoint (SSE) | [chat.py:794](../backend/app/features/rag_chatbot/api/chat.py#L794) |
| `CHAT-021` | `POST /feedback` — thumbs up/down | [chat.py:973](../backend/app/features/rag_chatbot/api/chat.py#L973) |
| `CHAT-022` | `GET /status` — LLM + retrieval provider status | [chat.py:1004](../backend/app/features/rag_chatbot/api/chat.py#L1004) |
| `CHAT-023` | `GET /index/status` — index file metadata (powers "Synced X ago") | [chat.py:1036](../backend/app/features/rag_chatbot/api/chat.py#L1036) |
| `CHAT-024` | `initialize_chat_system()` — defined but unused (dead code, noted) | [chat.py:1098](../backend/app/features/rag_chatbot/api/chat.py#L1098) |

## PVEC — pgvector fallback + audit trail (`.../vector/pgvector_store.py`)

The second half of dual-path retrieval, plus every write that makes the
"similar questions" feature and the dashboard's audit trail real.

| Tag | What | Location |
|---|---|---|
| `PVEC` | Module overview | [pgvector_store.py:5](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L5) |
| `PVEC-001` | `_get_service_client()` / `is_configured()` — service-role Supabase client | [pgvector_store.py:51](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L51) |
| `PVEC-002` | `_document_source_path()` — stable document identity key | [pgvector_store.py:93](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L93) |
| `PVEC-003` | `upsert_documents()` — dual-write to dim_document/fact_chunk/fact_embedding | [pgvector_store.py:110](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L110) |
| `PVEC-004` | `pgvector_search()` — the actual fallback query (calls `match_chunks()`) | [pgvector_store.py:252](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L252) |
| `PVEC-005` | `log_query()` — audit write: fact_query + bridge_query_citation | [pgvector_store.py:316](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L316) |
| `PVEC-006` | `SIMILAR_QUERY_THRESHOLD` + `upsert_query_embedding()` | [pgvector_store.py:430](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L430) |
| `PVEC-007` | `find_similar_queries()` — the real "similar questions" metric | [pgvector_store.py:479](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L479) |
| `PVEC-008` | `set_feedback()` — thumbs up/down write | [pgvector_store.py:545](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L545) |
| `PVEC-009` | `hydrate_index_from_supabase()` — rebuild JSON index from Postgres | [pgvector_store.py:575](../backend/app/features/rag_chatbot/vector/pgvector_store.py#L575) |

## IDX — primary retrieval path (`.../vector/persisted_inmemory_search.py`)

The in-memory JSON index searched first, plus the one shared embedding
function every other module reuses.

| Tag | What | Location |
|---|---|---|
| `IDX` | Module overview | [persisted_inmemory_search.py:2](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L2) |
| `IDX-001` | `_cosine()` / `_hash_to_vector()` — similarity math + mock embeddings | [persisted_inmemory_search.py:33](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L33) |
| `IDX-002` | `embed_texts()` — THE shared embedding entrypoint for the whole system | [persisted_inmemory_search.py:154](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L154) |
| `IDX-003` | `PersistedInMemorySearch.__init__()` / `_load_if_exists()` | [persisted_inmemory_search.py:216](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L216) |
| `IDX-004` | `ingest_texts()` / `ingest_documents()` — bulk embed + persist | [persisted_inmemory_search.py:316](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L316) |
| `IDX-005` | `search()` — brute-force cosine similarity, no ANN index | [persisted_inmemory_search.py:346](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L346) |
| `IDX-006` | `get_stats()` — index introspection | [persisted_inmemory_search.py:379](../backend/app/features/rag_chatbot/vector/persisted_inmemory_search.py#L379) |

## AUTH — authentication & role gating (`backend/app/core/`)

| Tag | What | Location |
|---|---|---|
| `AUTH` | Module overview — 3 layers: optional → strict → RBAC | [auth_deps.py:11](../backend/app/core/auth_deps.py#L11) |
| `AUTH-001` | `get_current_user_optional()` — root of every auth check | [auth_deps.py:24](../backend/app/core/auth_deps.py#L24) |
| `AUTH-002` | Supabase token verification module (not local JWT decode) | [supabase_jwt.py:27](../backend/app/core/supabase_jwt.py#L27) |
| `AUTH-002b` | `verify_supabase_token()` — calls Supabase Auth `get_user()` | [supabase_jwt.py:55](../backend/app/core/supabase_jwt.py#L55) |
| `AUTH-003` | `get_current_user()` — hard-401 variant | [auth_deps.py:58](../backend/app/core/auth_deps.py#L58) |
| `AUTH-004` | `require_roles()` — RBAC dependency factory | [auth_deps.py:69](../backend/app/core/auth_deps.py#L69) |
| `AUTH-005` | `require_roles_or_automation_token()` — RBAC + headless CI escape hatch | [auth_deps.py:104](../backend/app/core/auth_deps.py#L104) |

## RATE — rate limiting (`backend/app/core/rate_limit.py`)

| Tag | What | Location |
|---|---|---|
| `RATE-001` | `limiter` — shared slowapi instance, per-IP, 120/min default | [rate_limit.py:9](../backend/app/core/rate_limit.py#L9) |

## ADMIN — admin endpoints (`backend/app/features/rag_chatbot/api/`)

| Tag | What | Location |
|---|---|---|
| `ADMIN-001` | Module overview — admin-triggered reindex API | [discovery.py:34](../backend/app/features/rag_chatbot/api/discovery.py#L34) |
| `ADMIN-001a` | `_run_reindex()` — full pipeline: Drive scan → embed → dual-write | [discovery.py:64](../backend/app/features/rag_chatbot/api/discovery.py#L64) |
| `ADMIN-001b` | `POST /reindex` — kicks off `_run_reindex()` as a background task | [discovery.py:153](../backend/app/features/rag_chatbot/api/discovery.py#L153) |
| `ADMIN-001c` | `GET /reindex/status` — polled by dashboard + CI | [discovery.py:181](../backend/app/features/rag_chatbot/api/discovery.py#L181) |
| `ADMIN-002` | Module overview — dashboard metrics API | [admin_metrics.py:30](../backend/app/features/rag_chatbot/api/admin_metrics.py#L30) |
| `ADMIN-002a` | `GET /metrics` — dashboard aggregation endpoint | [admin_metrics.py:62](../backend/app/features/rag_chatbot/api/admin_metrics.py#L62) |
| `ADMIN-002b` | `_percentile()` — nearest-rank percentile for p95 latency | [admin_metrics.py:50](../backend/app/features/rag_chatbot/api/admin_metrics.py#L50) |

## ING — shared ingestion helpers + CLIs

| Tag | What | Location |
|---|---|---|
| `ING-001` | Module overview — chunking/extraction shared by both ingestion paths | [ingestion_common.py:9](../backend/app/features/rag_chatbot/ingestion_common.py#L9) |
| `ING-001a` | `FOLDER_DEPARTMENT_MAP` / `department_for_folder()` | [ingestion_common.py:27](../backend/app/features/rag_chatbot/ingestion_common.py#L27) |
| `ING-001b` | `chunk_text()` / `extract_text_from_*()` — chunking + per-format extraction | [ingestion_common.py:55](../backend/app/features/rag_chatbot/ingestion_common.py#L55) |
| `ING-001c` | `extract_table_chunks_from_xlsx_bytes()` — structure-preserving Excel | [ingestion_common.py:66](../backend/app/features/rag_chatbot/ingestion_common.py#L66) |
| `ING-001d` | `make_chunk_documents()` / `make_table_chunk_documents()` | [ingestion_common.py:153](../backend/app/features/rag_chatbot/ingestion_common.py#L153) |
| `ING-001e` | `backup_index_if_exists()` — pre-rebuild safety net | [ingestion_common.py:300](../backend/app/features/rag_chatbot/ingestion_common.py#L300) |
| `ING-002` | Module overview — real Google Drive ingestion CLI | [build_drive_index.py:53](../backend/build_drive_index.py#L53) |
| `ING-002a` | `discover_documents()` — the real Drive discovery loop | [build_drive_index.py:89](../backend/build_drive_index.py#L89) |
| `ING-002b` | `_looks_supported()` / `_get_bytes()` — MIME-type dispatch | [build_drive_index.py:77](../backend/build_drive_index.py#L77) |
| `ING-002c` | `main()` — CLI entrypoint | [build_drive_index.py:191](../backend/build_drive_index.py#L191) |
| `ING-002-local` | Module overview — local-folder ingestion CLI (Drive-free sibling) | [build_local_index.py:44](../backend/build_local_index.py#L44) |
| `ING-002-local-a` | `discover_documents()` — local variant | [build_local_index.py:59](../backend/build_local_index.py#L59) |
| `ING-002-local-b` | `main()` — CLI entrypoint | [build_local_index.py:122](../backend/build_local_index.py#L122) |

## DRIVE — Google Drive API client (`.../vector/google_drive_service.py`)

| Tag | What | Location |
|---|---|---|
| `DRIVE` | Module overview — active methods vs. legacy scaffolding | [google_drive_service.py:2](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L2) |
| `DRIVE-001` | `GoogleDriveService.__init__()` / `_connect()` — service-account auth | [google_drive_service.py:57](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L57) |
| `DRIVE-002` | `test_connection()` — cheap health check | [google_drive_service.py:112](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L112) |
| `DRIVE-003` | `find_finance_folder()` — generic folder-by-name lookup | [google_drive_service.py:135](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L135) |
| `DRIVE-004` | `list_all_files_in_folder()` — the actual file discovery call used today | [google_drive_service.py:542](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L542) |
| `DRIVE-005` | `download_file()` / `export_google_doc_as_text()` — the two byte-fetch paths | [google_drive_service.py:594](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L594) |
| `DRIVE-006` | Legacy finance-specific methods — **not** on the current ingestion path | [google_drive_service.py:182](../backend/app/features/rag_chatbot/vector/google_drive_service.py#L182) |

## LLM — generation layer (`backend/app/features/rag_chatbot/llm/`)

| Tag | What | Location |
|---|---|---|
| `LLM` | Module overview | [llm_client.py:3](../backend/app/features/rag_chatbot/llm/llm_client.py#L3) |
| `LLM-001` | `LLMClient` provider selection — **known bug**: OpenAI silently wins if both keys set | [llm_client.py:128](../backend/app/features/rag_chatbot/llm/llm_client.py#L128) |
| `LLM-002` | `OpenAILLM` — the OpenAI backend | [llm_client.py:37](../backend/app/features/rag_chatbot/llm/llm_client.py#L37) |
| `LLM-002b` | `GeminiLLM` — the Gemini backend (the one actually active in prod) | [llm_client.py:126](../backend/app/features/rag_chatbot/llm/llm_client.py#L126) |
| `LLM-003` | `LLMClient` — single entrypoint chat.py imports | [llm_client.py:215](../backend/app/features/rag_chatbot/llm/llm_client.py#L215) |
| `LLM-004` | Module overview — prompt assembly | [llm_client.py:135](../backend/app/features/rag_chatbot/llm/llm_client.py#L135) |
| `LLM-004a` | `create_prompt_engineering_system()` — static system prompt | [prompt_engineering.py:26](../backend/app/features/rag_chatbot/llm/prompt_engineering.py#L26) |
| `LLM-004b` | `PromptIntegrator` — folds context, own independent size cap | [prompt_engineering.py:95](../backend/app/features/rag_chatbot/llm/prompt_engineering.py#L95) |
| `LLM-004c` | `_classify_query()` — regex-based adaptive-length heuristic | [prompt_engineering.py:32](../backend/app/features/rag_chatbot/llm/prompt_engineering.py#L32) |
| `LLM-004d` | `get_prompt_for_query()` — the function chat.py actually calls | [prompt_engineering.py:166](../backend/app/features/rag_chatbot/llm/prompt_engineering.py#L166) |

## SCHEMA — database schema (`backend/sql/schema.sql`)

| Tag | What | Location |
|---|---|---|
| `SCHEMA` | Module overview | [schema.sql:37](../backend/sql/schema.sql#L37) |
| `SCHEMA-001` | `dim_document` — document registry | [schema.sql:48](../backend/sql/schema.sql#L48) |
| `SCHEMA-002` | `fact_chunk` — retrieval-granularity chunks | [schema.sql:67](../backend/sql/schema.sql#L67) |
| `SCHEMA-002b` | `fact_embedding` — the pgvector fallback store, `VECTOR(1536)` | [schema.sql:85](../backend/sql/schema.sql#L85) |
| `SCHEMA-002c` | No ANN index yet — confirmed: every query today is exact/sequential | [schema.sql:101](../backend/sql/schema.sql#L101) |
| `SCHEMA-003` | `match_chunks()` RPC — the pgvector fallback query | [schema.sql:173](../backend/sql/schema.sql#L173) |
| `SCHEMA-003b` | `fact_query` — audit log | [schema.sql:121](../backend/sql/schema.sql#L121) |
| `SCHEMA-003c` | `fact_query_embedding` — powers "similar questions" | [schema.sql:143](../backend/sql/schema.sql#L143) |
| `SCHEMA-004` | `match_queries()` RPC — similar-question lookup | [schema.sql:224](../backend/sql/schema.sql#L224) |
| `SCHEMA-004b` | `bridge_query_citation` — one row per cited source | [schema.sql:157](../backend/sql/schema.sql#L157) |
| `SCHEMA-005` | Row Level Security — why service-role bypasses it, why no write policies | [schema.sql:262](../backend/sql/schema.sql#L262) |

## MAIN — app factory & startup (`backend/app/main.py`)

| Tag | What | Location |
|---|---|---|
| `MAIN` | Module overview | [main.py:3](../backend/app/main.py#L3) |
| `MAIN-002` | `lifespan()` — hydrate index from Supabase on ephemeral-disk restart | [main.py:89](../backend/app/main.py#L89) |
| `MAIN-003` | `create_app()` — rate limiter, CORS, router registration | [main.py:165](../backend/app/main.py#L165) |

## CI — GitHub Actions workflows (`.github/workflows/`)

| Tag | What | Location |
|---|---|---|
| `CI-001` | Module overview — daily automated reindex trigger | [scheduled-reindex.yml:4](../.github/workflows/scheduled-reindex.yml#L4) |
| `CI-001a` | Trigger step — `POST /reindex`, 200/409 both treated as success | [scheduled-reindex.yml:26](../.github/workflows/scheduled-reindex.yml#L26) |
| `CI-001b` | Poll step — `GET /reindex/status` every 15s, up to 15 min | [scheduled-reindex.yml:42](../.github/workflows/scheduled-reindex.yml#L42) |
| `CI-002` | Pull-request / push CI — pytest, lint, unit tests, build | [ci.yml:1](../.github/workflows/ci.yml#L1) |
| `CI-002b` | Smoke-import step — catches boot-time import errors pytest can't | [ci.yml:43](../.github/workflows/ci.yml#L43) |

## FE-CHAT — chat UI (`frontend/src/app/page.tsx`)

| Tag | What | Location |
|---|---|---|
| `FE-CHAT` | Module overview — mirrors backend SSE/ChatResponse shapes by hand | [page.tsx:47](../frontend/src/app/page.tsx#L47) |
| `FE-CHAT-a` | `SourceClusters` — always-visible department badges | [page.tsx:279](../frontend/src/app/page.tsx#L279) |
| `FE-CHAT-b` | `SourcesToggle` — real `<button>` disclosure, not disguised `<details>` | [page.tsx:304](../frontend/src/app/page.tsx#L304) |
| `FE-CHAT-c` | `SimilarQuestions` — renders the real cosine-similarity metric | [page.tsx:347](../frontend/src/app/page.tsx#L347) |
| `FE-CHAT-d` | `TracePanel` — retrieval-transparency panel | [page.tsx:405](../frontend/src/app/page.tsx#L405) |
| `FE-CHAT-SSE` | `sendMessage()` — hand-rolled SSE client (fetch + getReader, not EventSource) | [page.tsx:582](../frontend/src/app/page.tsx#L582) |

## FE-DASH — dashboard (`frontend/src/app/dashboard/page.tsx`)

| Tag | What | Location |
|---|---|---|
| `FE-DASH` | Module overview | [dashboard/page.tsx:35](../frontend/src/app/dashboard/page.tsx#L35) |
| `FE-DASH-a` | `ReindexButton` — trigger + self-rescheduling poll loop | [dashboard/page.tsx:40](../frontend/src/app/dashboard/page.tsx#L40) |
| `FE-DASH-b` | Metrics fetch effect — re-runs on window/session change | [dashboard/page.tsx:272](../frontend/src/app/dashboard/page.tsx#L272) |

## FE-LOGIN — sign-in/sign-up (`frontend/src/app/login/page.tsx`)

| Tag | What | Location |
|---|---|---|
| `FE-LOGIN` | Module overview — 3-mode state machine, talks to Supabase directly | [login/page.tsx:9](../frontend/src/app/login/page.tsx#L9) |
| `FE-LOGIN-a` | `submit()` — sign-in/sign-up, confirm-pending branching | [login/page.tsx:30](../frontend/src/app/login/page.tsx#L30) |

## FE-LIB — shared frontend helpers (`frontend/src/lib/`)

| Tag | What | Location |
|---|---|---|
| `FE-LIB-001` | `supabase` client — browser-side, anon key only | [supabaseClient.ts:1](../frontend/src/lib/supabaseClient.ts#L1) |
| `FE-LIB-002` | Module overview — chat/dashboard helpers | [chatUtils.ts:1](../frontend/src/lib/chatUtils.ts#L1) |
| `FE-LIB-002b` | `formatRelativeTime()` — powers the "Synced X ago" badge | [chatUtils.ts:23](../frontend/src/lib/chatUtils.ts#L23) |

---

## Known issues flagged inline (worth knowing before a live Q&A)

- **`[OPS:LLM-001]`** — if both `OPENAI_API_KEY` and `GEMINI_API_KEY` are
  set, OpenAI silently wins over Gemini (the provider this deployment
  actually intends to run on). Same bug shape independently exists in
  `[OPS:IDX-002]` `embed_texts()`.
- **`[OPS:CHAT-024]`** — `initialize_chat_system()` is defined but nothing
  calls it; `[OPS:MAIN-002]` `lifespan()` reimplements an equivalent check
  inline instead.
- **`[OPS:DRIVE-006]`** — a block of earlier, finance-file-specific Drive
  methods (`list_excel_files`, `list_target_finance_files`, etc.) predates
  the current generic ingestion pipeline and isn't called by anything
  today; not deleted, just dormant.
- **`[OPS:SCHEMA-002c]`** — confirmed live via grep: no `ivfflat`/`hnsw`
  index currently exists on `fact_embedding`; every pgvector query today
  is an exact sequential scan (correct at this corpus size, ~117 chunks).
- **`[OPS:LLM-004b]`** — two independent, uncoordinated context-size
  budgets exist in sequence: `[OPS:CHAT-014]`'s token-based budget (~6000
  tokens), then `PromptIntegrator`'s own separate character-based cap
  (4000 chars) on top.
