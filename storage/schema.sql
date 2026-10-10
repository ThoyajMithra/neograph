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



CREATE TABLE IF NOT EXISTS nodes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    node_type        TEXT NOT NULL DEFAULT 'UNKNOWN',
    aliases          TEXT[] NOT NULL DEFAULT '{}',
    description      TEXT NOT NULL DEFAULT '',
    source_chunk_ids UUID[] NOT NULL DEFAULT '{}',
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    embedding        VECTOR(384)
);

CREATE TABLE IF NOT EXISTS edges (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id       UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id       UUID NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    relation        TEXT NOT NULL,
    source_chunk_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (source_id <> target_id),
    UNIQUE (source_id, target_id, relation)      -- save_edge returns False on duplicates
);

CREATE TABLE IF NOT EXISTS traces (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question        TEXT NOT NULL,
    entry_nodes     UUID[] NOT NULL DEFAULT '{}',
    visited_nodes   UUID[] NOT NULL DEFAULT '{}',
    traversed_edges JSONB NOT NULL DEFAULT '[]',
    source_chunks   UUID[] NOT NULL DEFAULT '{}',
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS nodes_type_idx          ON nodes (node_type);
CREATE INDEX IF NOT EXISTS nodes_source_chunks_idx ON nodes USING gin (source_chunk_ids);
CREATE INDEX IF NOT EXISTS nodes_embedding_idx     ON nodes USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS edges_source_idx        ON edges (source_id);
CREATE INDEX IF NOT EXISTS edges_target_idx        ON edges (target_id);
CREATE INDEX IF NOT EXISTS edges_relation_idx      ON edges (relation);
CREATE INDEX IF NOT EXISTS traces_question_idx     ON traces (question);




CREATE OR REPLACE FUNCTION match_nodes(query_embedding VECTOR(384), match_count INT DEFAULT 5)
RETURNS TABLE (id UUID, score DOUBLE PRECISION)
LANGUAGE sql STABLE AS $$
    SELECT n.id, 1 - (n.embedding <=> query_embedding)
    FROM nodes n
    WHERE n.embedding IS NOT NULL
    ORDER BY n.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION match_chunks(query_embedding VECTOR(384), match_count INT DEFAULT 5)
RETURNS TABLE (id UUID, score DOUBLE PRECISION)
LANGUAGE sql STABLE AS $$
    SELECT c.id, 1 - (c.embedding <=> query_embedding)
    FROM chunks c
    WHERE c.embedding IS NOT NULL
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
$$;



CREATE OR REPLACE FUNCTION graph_metrics()
RETURNS TABLE (node_count BIGINT, edge_count BIGINT, chunk_count BIGINT, document_count BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT
        (SELECT count(*) FROM nodes),
        (SELECT count(*) FROM edges),
        (SELECT count(*) FROM chunks),
        (SELECT count(*) FROM documents);
$$;

CREATE OR REPLACE FUNCTION graph_node_type_distribution()
RETURNS TABLE (label TEXT, value BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT upper(node_type), count(*)
    FROM nodes
    GROUP BY upper(node_type) ORDER BY count(*) DESC;
$$;

CREATE OR REPLACE FUNCTION graph_relation_distribution(p_top_k INT DEFAULT 15)
RETURNS TABLE (label TEXT, value BIGINT)
LANGUAGE sql STABLE AS $$
    SELECT relation, count(*)
    FROM edges
    GROUP BY relation ORDER BY count(*) DESC LIMIT p_top_k;
$$;

CREATE OR REPLACE FUNCTION graph_top_nodes_by_degree(p_top_k INT DEFAULT 10)
RETURNS TABLE (id UUID, label TEXT, type TEXT, value BIGINT)
LANGUAGE sql STABLE AS $$
    WITH deg AS (
        SELECT node_id, count(*) AS d FROM (
            SELECT source_id AS node_id FROM edges
            UNION ALL
            SELECT target_id FROM edges
        ) x GROUP BY node_id
    )
    SELECT n.id, n.name, n.node_type, coalesce(deg.d, 0)
    FROM nodes n LEFT JOIN deg ON deg.node_id = n.id
    ORDER BY coalesce(deg.d, 0) DESC, n.name
    LIMIT p_top_k;
$$;

CREATE OR REPLACE FUNCTION graph_degree_distribution()
RETURNS TABLE (label TEXT, value BIGINT)
LANGUAGE sql STABLE AS $$
    WITH deg AS (
        SELECT n.id, count(e.id) AS d
        FROM nodes n
        LEFT JOIN edges e ON e.source_id = n.id OR e.target_id = n.id
        GROUP BY n.id
    ),
    buckets(label, lo, hi, ord) AS (
        VALUES ('0',0,0,1), ('1',1,1,2), ('2',2,2,3),
               ('3-5',3,5,4), ('6-10',6,10,5), ('11+',11,2147483647,6)
    )
    SELECT b.label, count(deg.id)
    FROM buckets b LEFT JOIN deg ON deg.d BETWEEN b.lo AND b.hi
    GROUP BY b.label, b.ord ORDER BY b.ord;
$$;

CREATE OR REPLACE FUNCTION graph_document_stats()
RETURNS TABLE (id UUID, label TEXT, chunks BIGINT, entities BIGINT, ingested_at TIMESTAMPTZ)
LANGUAGE sql STABLE AS $$
    SELECT
        d.id, d.name,
        (SELECT count(*) FROM chunks c WHERE c.document_id = d.id),
        (SELECT count(*) FROM nodes n
          WHERE EXISTS (SELECT 1 FROM chunks c
                        WHERE c.document_id = d.id AND c.id = ANY(n.source_chunk_ids))),
        d.created_at
    FROM documents d
    ORDER BY d.created_at DESC;
$$;