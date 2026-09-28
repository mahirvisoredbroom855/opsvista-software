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

-- ─────────────────────────────────────────────────────────────────────────
-- MODULE: [OPS:SCHEMA]
--
-- What it does: the backup search database plus a full audit trail —
-- documents, their chunks, each chunk's numeric fingerprint, and a log
-- of every question ever asked (for the dashboard). Written to by
-- pgvector_store.py's upsert/log functions; read by the backup search
-- and the similar-questions feature.
-- ─────────────────────────────────────────────────────────────────────────

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-001] dim_document
--
-- What it does: one row per source document (a Google Drive file, or a
-- local test file), identified by its source type plus its path. This
-- identity key must match exactly what the Python ingestion code
-- computes for the same document, or the same document would get
-- treated as a new one on every reindex instead of being updated.
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
-- [OPS:SCHEMA-002] fact_chunk
--
-- What it does: one row per searchable chunk of text — the exact same
-- chunks the local JSON index stores. `ordinal` records each chunk's
-- position within its document, and the (document_id, ordinal) pair
-- together is what upsert_documents() uses to detect "this is the same
-- chunk as before, update it" instead of creating a duplicate.
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
-- [OPS:SCHEMA-002b] fact_embedding
--
-- What it does: stores each chunk's numeric fingerprint — the actual
-- data the backup search compares against. It's written at the same
-- time as the local JSON index, by the same ingestion step, so both
-- copies always stay in sync. The vector is 1536 numbers wide, not
-- Gemini's native 3072, because it's shrunk to fit under pgvector's own
-- 2000-dimension index limit (see the file header note).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_embedding (
    chunk_id       UUID PRIMARY KEY REFERENCES fact_chunk(chunk_id) ON DELETE CASCADE,
    model          TEXT NOT NULL,
    dim            INT NOT NULL,
    embedding      VECTOR(1536) NOT NULL,
    generated_at   TIMESTAMPTZ DEFAULT now()
);

-- [OPS:SCHEMA-002c] No search index on this column, deliberately
--
-- What this means: every backup search today checks every single row
-- one by one (a plain sequential scan), rather than using a fast
-- approximate search index. That's intentional — with only a few
-- hundred rows in this corpus, adding an approximate-search index would
-- actually make results WORSE (too few rows per cluster to approximate
-- well) while gaining no real speed. A plain scan is both more accurate
-- and fast enough below roughly 1,000-10,000 rows. Add an index back
-- once the corpus grows past that:
--
--   CREATE INDEX idx_fact_embedding_vector ON fact_embedding
--       USING ivfflat (embedding vector_cosine_ops)
--       WITH (lists = <row_count / 1000, minimum 10>);
--
-- (or use HNSW instead, which degrades less at small scale but costs more
-- to build: `USING hnsw (embedding vector_cosine_ops)`).

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-003b] fact_query
--
-- What it does: one row logged for every single chat question asked —
-- the question text, how long it took, whether the backup search ran,
-- and the token counts. Written automatically on every chat request;
-- user_rating gets filled in separately, later, when someone clicks
-- thumbs up or down on the answer.
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
-- [OPS:SCHEMA-003c] fact_query_embedding
--
-- What it does: stores a numeric fingerprint of every past question
-- that's been asked, so a new question can be compared against real
-- prior ones and show "N similar questions asked before" — a genuine
-- comparison, not a fake or hardcoded number.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_query_embedding (
    query_id      UUID PRIMARY KEY REFERENCES fact_query(query_id) ON DELETE CASCADE,
    embedding     VECTOR(1536) NOT NULL,
    generated_at  TIMESTAMPTZ DEFAULT now()
);

-- [OPS:SCHEMA-004b] bridge_query_citation
--
-- What it does: one row per source document actually cited in an
-- answer, in the order they were ranked. This is what the "most-cited
-- documents" and "most-cited departments" numbers on the dashboard are
-- computed from.
CREATE TABLE IF NOT EXISTS bridge_query_citation (
    query_id         UUID REFERENCES fact_query(query_id) ON DELETE CASCADE,
    document_id      UUID REFERENCES dim_document(document_id),
    chunk_id         UUID REFERENCES fact_chunk(chunk_id),
    relevance_score  NUMERIC(5,4),
    rank             INT,
    PRIMARY KEY (query_id, chunk_id)
);

-- ---------------------------------------------------------------------------
-- [OPS:SCHEMA-003] match_chunks()
--
-- What it does: the actual backup search query — given a question's
-- numeric fingerprint, finds the closest-matching chunks. It's written
-- as a database function (not a plain query) because Supabase's normal
-- API can't express the "how similar are these two vectors" comparison
-- directly. The embedding is passed in as a text string, not a native
-- vector type, because that conversion path is the one pgvector
-- guarantees will always work reliably. The math flips "distance"
-- (0 = identical) into "similarity" (1 = identical), so scores read the
-- same way as the primary index's own similarity scores.
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
-- [OPS:SCHEMA-004] match_queries()
--
-- What it does: same idea as match_chunks(), but searches past
-- questions instead of document chunks — this is what powers "similar
-- questions asked before". exclude_query_id lets the caller make sure
-- the current in-flight question can't match itself in its own results
-- (a safety guard — in practice the current question's own fingerprint
-- isn't even saved yet when this runs, so it usually couldn't match
-- itself anyway).
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
-- What it does: these rules are enforced by the database itself, not
-- just by the backend's code — so even a direct table read using only
-- the public anon key stays restricted, even if the backend's own login
-- check were somehow bypassed. Any logged-in user can read the
-- knowledge-base tables (documents, chunks, embeddings), but only the
-- ingestion scripts can write to them, using a separate secret key that
-- skips these rules entirely by Supabase's design. A user can only ever
-- read their OWN past questions, never anyone else's. There are no
-- write rules defined below on purpose — since only that secret-key
-- writer ever writes, and it always skips these rules anyway.
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
