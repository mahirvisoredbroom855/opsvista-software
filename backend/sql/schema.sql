-- OpsVista RAG — Supabase schema
--
-- This file creates every table the backend needs in the Supabase
-- database: one for source documents, one for the small chunks each
-- document gets cut into, one for each chunk's numeric fingerprint
-- (used by the backup search), and three more that log every question
-- ever asked, for the observability dashboard. Run this once in a
-- fresh Supabase project's SQL Editor to set everything up.
--
-- Implements the data contract from the Development Specification
-- (Section 13.4.1, "Core Tables (Supabase/PostgreSQL)") plus the pgvector
-- fallback path described in the RAG Documentation's dual-path retrieval
-- design (enhanced_index.json = primary, pgvector = fallback).
--
-- Run this once against a fresh Supabase project:
--   Dashboard -> SQL Editor -> paste this file -> Run
--
-- IMPORTANT: the embedding column below is fixed at 1536 dimensions.
-- gemini-embedding-001 natively outputs 3072 dims, but pgvector's ivfflat/
-- hnsw indexes cap out at 2000 dimensions — so the embedding call requests
-- a smaller output via Matryoshka representation learning
-- (GEMINI_EMBEDDING_DIM=1536 in .env, passed as output_dimensionality to the
-- API in persisted_inmemory_search.py). If you change embedding provider or
-- dimension, this table must be dropped and recreated with the new width,
-- and the index rebuilt via build_local_index.py / build_drive_index.py --reset.
--
-- Safe to re-run: drops any partial state from a previous failed attempt
-- (e.g. the ivfflat dimension-limit error) before recreating everything.
DROP FUNCTION IF EXISTS match_chunks(vector, int);
DROP FUNCTION IF EXISTS match_chunks(text, int);
DROP FUNCTION IF EXISTS match_queries(vector, int, uuid);
DROP FUNCTION IF EXISTS match_queries(text, int, uuid);
DROP TABLE IF EXISTS bridge_query_citation CASCADE;
DROP TABLE IF EXISTS fact_query_embedding CASCADE;
DROP TABLE IF EXISTS fact_query CASCADE;
DROP TABLE IF EXISTS fact_embedding CASCADE;
DROP TABLE IF EXISTS fact_chunk CASCADE;
DROP TABLE IF EXISTS dim_document CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

-- ═══════════════════════════════════════════════════════════════════════
-- MODULE: [OPS:SCHEMA] — the pgvector fallback + audit-trail schema
--
-- Written to by [OPS:PVEC-003] upsert_documents() (dim_document/fact_chunk/
-- fact_embedding), [OPS:PVEC-005] log_query() (fact_query/
-- bridge_query_citation), [OPS:PVEC-006] upsert_query_embedding()
-- (fact_query_embedding). Read by [OPS:PVEC-004] pgvector_search() (via
-- match_chunks() [OPS:SCHEMA-003]) and [OPS:PVEC-007] find_similar_queries()
-- (via match_queries() [OPS:SCHEMA-004]).
-- ═══════════════════════════════════════════════════════════════════════

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-001] dim_document — one row per source document (Drive file or
-- local seed_docs file), keyed by (source_type, source_path) — the same
-- identity key [OPS:PVEC-002] _document_source_path() computes in Python, so
-- the two must always agree or upserts/citations silently fail to match.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_document (
    document_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type       TEXT NOT NULL,           -- 'google_drive' | 'local_seed' | 'other'
    source_path       TEXT NOT NULL,           -- drive_file_id, or local relative path
    title             TEXT,
    department        TEXT,                    -- HR | Finance | Commercial | Admin | Maintenance | Accounting
    classification    TEXT DEFAULT 'internal',
    last_modified_at  TIMESTAMPTZ,
    discovered_at     TIMESTAMPTZ DEFAULT now(),
    is_active         BOOLEAN DEFAULT TRUE,
    UNIQUE (source_type, source_path)
);

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-002] fact_chunk — one row per retrieval-granularity chunk,
-- matching exactly what the enhanced_index.json ingestion pipeline
-- ([OPS:ING-001d] make_chunk_documents()) already produces. `ordinal` is the
-- same value as the Python-side chunk_index metadata field — the
-- (document_id, ordinal) unique constraint is pgvector_store.py's upsert
-- conflict key [OPS:PVEC-003].
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_chunk (
    chunk_id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id   UUID REFERENCES dim_document(document_id) ON DELETE CASCADE,
    ordinal       INT NOT NULL,
    text          TEXT NOT NULL,
    metadata      JSONB DEFAULT '{}'::jsonb,    -- carries the same metadata as the JSON index (table data, etc.)
    created_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE (document_id, ordinal)
);

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-002b] fact_embedding — the actual pgvector fallback store.
-- Spec note: "vectors reside in enhanced_index.json or pgvector" — here they
-- reside in BOTH, written by the same ingestion pass (dual-write via
-- [OPS:PVEC-003] upsert_documents()), so the fallback path has real, current
-- data rather than a hollow adapter. VECTOR(1536), not Gemini's native 3072
-- — see the file header comment for why (Matryoshka truncation, pgvector's
-- ivfflat/hnsw 2000-dim cap).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_embedding (
    chunk_id       UUID PRIMARY KEY REFERENCES fact_chunk(chunk_id) ON DELETE CASCADE,
    model          TEXT NOT NULL,
    dim            INT NOT NULL,
    embedding      VECTOR(1536) NOT NULL,
    generated_at   TIMESTAMPTZ DEFAULT now()
);

-- [OPS:SCHEMA-002c] No ANN index yet, deliberately — confirmed live: every
-- pgvector similarity search today (match_chunks/match_queries) is an exact
-- sequential scan, not an ivfflat/hnsw-indexed approximate search. pgvector's
-- guidance is roughly
-- `lists = rows / 1000` for ivfflat — with a few hundred rows in this
-- corpus, that rounds to ~0-1 lists, meaning an index here would make
-- search *worse* (each cluster ends up with ~1 vector, badly approximating
-- true nearest neighbors) while adding no speed benefit at this scale.
-- Exact search (a plain sequential scan) is both more accurate and fast
-- enough below roughly 1000-10,000 rows. Add this back once the corpus is
-- large enough to need it:
--
--   CREATE INDEX idx_fact_embedding_vector ON fact_embedding
--       USING ivfflat (embedding vector_cosine_ops)
--       WITH (lists = <row_count / 1000, minimum 10>);
--
-- (or use HNSW instead, which degrades less at small scale but costs more
-- to build: `USING hnsw (embedding vector_cosine_ops)`).

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-003b] fact_query — query audit log (operational transparency /
-- compliance, per spec section 8 "Operational Monitoring" and 14 "Privacy
-- Policy & Data Compliance"). Written by [OPS:PVEC-005] log_query() on every
-- chat request; user_rating written separately by [OPS:PVEC-008]
-- set_feedback() when the user clicks thumbs up/down.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_query (
    query_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id               UUID,                -- from Supabase auth; NULL for pre-auth requests
    query_text            TEXT NOT NULL,
    top_k                 INT DEFAULT 4,
    used_fallback         BOOLEAN DEFAULT FALSE,
    retrieval_confidence  NUMERIC(5,4),
    processing_time_ms    INT,
    prompt_tokens         INT,
    completion_tokens     INT,
    total_tokens          INT,
    user_rating           TEXT CHECK (user_rating IN ('up', 'down')),
    created_at            TIMESTAMPTZ DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-003c] fact_query_embedding — powers the "similar questions
-- others are asking" UI feature. Same pattern as fact_embedding/
-- match_chunks (dual-path retrieval), applied to past *queries* instead of
-- document chunks: every answered query gets embedded and stored here
-- (via [OPS:PVEC-006] upsert_query_embedding()), so a new question can be
-- compared against real prior questions via cosine similarity rather than
-- a fake/static number. Read by match_queries() [OPS:SCHEMA-004].
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_query_embedding (
    query_id      UUID PRIMARY KEY REFERENCES fact_query(query_id) ON DELETE CASCADE,
    embedding     VECTOR(1536) NOT NULL,
    generated_at  TIMESTAMPTZ DEFAULT now()
);

-- [OPS:SCHEMA-004b] bridge_query_citation — one row per source cited in an
-- answer (rank-ordered). Written by [OPS:PVEC-005] log_query(), which
-- re-derives document_id/chunk_id via the same lookup keys
-- [OPS:PVEC-003] upsert_documents() wrote them under. Read by
-- [OPS:ADMIN-002a] GET /metrics for the top-documents/top-departments
-- aggregation.
CREATE TABLE IF NOT EXISTS bridge_query_citation (
    query_id         UUID REFERENCES fact_query(query_id) ON DELETE CASCADE,
    document_id      UUID REFERENCES dim_document(document_id),
    chunk_id         UUID REFERENCES fact_chunk(chunk_id),
    relevance_score  NUMERIC(5,4),
    rank             INT,
    PRIMARY KEY (query_id, chunk_id)
);

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-003] match_chunks() — the actual pgvector fallback query.
-- supabase-py's REST interface can't express the `<=>` distance operator
-- directly, so it's exposed as a Postgres function and called via
-- .rpc("match_chunks", {...}) from [OPS:PVEC-004] pgvector_search().
--
-- query_embedding is accepted as TEXT (a JSON-array string like
-- "[0.01,-0.02,...]") rather than VECTOR directly — PostgREST's JSON->vector
-- coercion over RPC is unreliable, whereas text->vector casting (see the
-- `::vector` cast in the SELECT below) is pgvector's documented,
-- guaranteed-stable input path. `1 - (embedding <=> query_embedding)`
-- converts cosine DISTANCE (0=identical) into cosine SIMILARITY
-- (1=identical) — the same convention [OPS:IDX-001] _cosine() returns on
-- the primary-index side, so scores from both retrieval paths read the
-- same way to a human even though they're computed on different machines.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding TEXT,
    match_count INT DEFAULT 4
)
RETURNS TABLE (
    chunk_id      UUID,
    document_id   UUID,
    text          TEXT,
    metadata      JSONB,
    similarity    FLOAT,
    title         TEXT,
    department    TEXT,
    source_type   TEXT,
    source_path   TEXT
)
LANGUAGE sql STABLE
AS $$
    SELECT
        fc.chunk_id,
        fc.document_id,
        fc.text,
        fc.metadata,
        1 - (fe.embedding <=> query_embedding::vector) AS similarity,
        dd.title,
        dd.department,
        dd.source_type,
        dd.source_path
    FROM fact_embedding fe
    JOIN fact_chunk fc ON fc.chunk_id = fe.chunk_id
    JOIN dim_document dd ON dd.document_id = fc.document_id
    WHERE dd.is_active = TRUE
    ORDER BY fe.embedding <=> query_embedding::vector
    LIMIT match_count;
$$;

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-004] match_queries() — finds prior questions similar to a new
-- one, via the same text->vector RPC pattern as match_chunks()
-- [OPS:SCHEMA-003] (see its comment for why TEXT, not VECTOR, is the
-- parameter type). Called via .rpc("match_queries", {...}) from
-- [OPS:PVEC-007] find_similar_queries(). exclude_query_id lets a caller
-- keep the current in-flight query out of its own "similar questions"
-- result — though in practice this is somewhat redundant with the ordering
-- guarantee in [OPS:PVEC-006]: the current query's own embedding isn't
-- written to fact_query_embedding until AFTER its similar-queries lookup
-- already ran, so it usually can't match itself anyway; exclude_query_id is
-- the explicit belt-and-suspenders guard for that ordering.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION match_queries(
    query_embedding TEXT,
    match_count INT DEFAULT 5,
    exclude_query_id UUID DEFAULT NULL
)
RETURNS TABLE (
    query_id    UUID,
    query_text  TEXT,
    similarity  FLOAT,
    created_at  TIMESTAMPTZ
)
LANGUAGE sql STABLE
AS $$
    SELECT
        fq.query_id,
        fq.query_text,
        1 - (fqe.embedding <=> query_embedding::vector) AS similarity,
        fq.created_at
    FROM fact_query_embedding fqe
    JOIN fact_query fq ON fq.query_id = fqe.query_id
    WHERE exclude_query_id IS NULL OR fqe.query_id != exclude_query_id
    ORDER BY fqe.embedding <=> query_embedding::vector
    LIMIT match_count;
$$;

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-005] Row Level Security
--
-- Enforced at the DATABASE level, not just in application code — this is
-- what [OPS:AUTH-002] verify_supabase_token()'s anon-key client actually
-- relies on: an anon-key client making a direct table read is still
-- restricted by these policies even if the backend's own auth check were
-- ever bypassed. All backend writes (ingestion, audit logging) instead use
-- the service-role client ([OPS:PVEC-001] _get_service_client()), which
-- bypasses RLS entirely by Supabase design — that's WHY there are no
-- INSERT/UPDATE/DELETE policies defined below: they'd be dead code, since
-- the only writer never goes through the policy-checked path.
--
-- Reasoning: the knowledge corpus tables (dim_document/fact_chunk/
-- fact_embedding) are read-only internal reference data — any authenticated
-- user may read them for retrieval, but only the ingestion pipeline (using
-- the service_role key, which bypasses RLS entirely by Supabase design) may
-- write to them. The audit tables (fact_query/bridge_query_citation) are
-- per-user: once real Supabase auth is wired up, a user should only ever
-- see their own query history, never anyone else's.
-- ---------------------------------------------------------------------------
ALTER TABLE dim_document ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_chunk ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_embedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_query ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_query_embedding ENABLE ROW LEVEL SECURITY;
ALTER TABLE bridge_query_citation ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS authenticated_read_documents ON dim_document;
CREATE POLICY authenticated_read_documents ON dim_document
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS authenticated_read_chunks ON fact_chunk;
CREATE POLICY authenticated_read_chunks ON fact_chunk
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS authenticated_read_embeddings ON fact_embedding;
CREATE POLICY authenticated_read_embeddings ON fact_embedding
    FOR SELECT TO authenticated USING (true);

DROP POLICY IF EXISTS users_read_own_queries ON fact_query;
CREATE POLICY users_read_own_queries ON fact_query
    FOR SELECT TO authenticated USING (auth.uid() = user_id);

DROP POLICY IF EXISTS users_read_own_citations ON bridge_query_citation;
CREATE POLICY users_read_own_citations ON bridge_query_citation
    FOR SELECT TO authenticated USING (
        EXISTS (
            SELECT 1 FROM fact_query fq
            WHERE fq.query_id = bridge_query_citation.query_id
              AND fq.user_id = auth.uid()
        )
    );

-- No INSERT/UPDATE/DELETE policies are defined for anon/authenticated on any
-- table above — by default that means those roles cannot write at all. Only
-- the service_role key (used by the ingestion scripts and the backend's
-- audit-logging call) can write, since service_role bypasses RLS by design.
