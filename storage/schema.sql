CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name       TEXT NOT NULL,
    content    TEXT NOT NULL,
    checksum   TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunks (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    idx         INTEGER NOT NULL,
    heading     TEXT,
    text        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding   VECTOR(384)
);

CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks (document_id);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);


CREATE TABLE IF NOT EXISTS chat_messages (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    sources    JSONB,
    confidence DOUBLE PRECISION,
    latency_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);