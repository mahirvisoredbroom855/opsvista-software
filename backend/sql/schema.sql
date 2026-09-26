-- OpsVista RAG — Supabase schema
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
DROP TABLE IF EXISTS bridge_query_citation CASCADE;
DROP TABLE IF EXISTS fact_query CASCADE;
DROP TABLE IF EXISTS fact_embedding CASCADE;
DROP TABLE IF EXISTS fact_chunk CASCADE;
DROP TABLE IF EXISTS dim_document CASCADE;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto; -- for gen_random_uuid()

-- ---------------------------------------------------------------------------
-- Document registry
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
-- Text chunks (one row per retrieval-granularity chunk, matching what the
-- enhanced_index.json ingestion pipeline already produces)
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
-- Embeddings — the actual pgvector fallback store. Spec note: "vectors
-- reside in enhanced_index.json or pgvector" — here they reside in both,
-- written by the same ingestion pass (dual-write), so the fallback path has
-- real, current data rather than a hollow adapter.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_embedding (
    chunk_id       UUID PRIMARY KEY REFERENCES fact_chunk(chunk_id) ON DELETE CASCADE,
    model          TEXT NOT NULL,
    dim            INT NOT NULL,
    embedding      VECTOR(1536) NOT NULL,
    generated_at   TIMESTAMPTZ DEFAULT now()
);

-- No ANN index yet, deliberately. pgvector's guidance is roughly
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
-- Query audit log (operational transparency / compliance, per spec section
-- 8 "Operational Monitoring" and 14 "Privacy Policy & Data Compliance")
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

CREATE TABLE IF NOT EXISTS bridge_query_citation (
    query_id         UUID REFERENCES fact_query(query_id) ON DELETE CASCADE,
    document_id      UUID REFERENCES dim_document(document_id),
    chunk_id         UUID REFERENCES fact_chunk(chunk_id),
    relevance_score  NUMERIC(5,4),
    rank             INT,
    PRIMARY KEY (query_id, chunk_id)
);

-- ---------------------------------------------------------------------------
-- match_chunks(): the actual pgvector fallback query. supabase-py's REST
-- interface can't express the `<=>` distance operator directly, so it's
-- exposed as a Postgres function and called via .rpc("match_chunks", {...}).
--
-- query_embedding is accepted as TEXT (a JSON-array string like
-- "[0.01,-0.02,...]") rather than VECTOR directly — PostgREST's JSON->vector
-- coercion over RPC is unreliable, whereas text->vector casting is pgvector's
-- documented, guaranteed-stable input path.
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
-- Row Level Security
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
