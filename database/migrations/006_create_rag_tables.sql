-- =============================================================
-- Migration 006 — RAG Knowledge Base Tables
-- HEATWATCH Database
-- =============================================================
-- Tables: rag_documents, rag_chunks
--
-- Depends on: 000, 001
--
-- SCOPE BOUNDARY — What belongs in RAG:
--   ✓ Scientific papers on fire behavior and industrial emissions
--   ✓ Sensor/satellite product documentation
--   ✓ Classification policy documents
--   ✓ Evidence policy documents
--   ✓ Verified case summaries (human-written)
--   ✓ Model documentation and changelogs
--   ✗ Raw hotspot pixel data (→ hotspots table)
--   ✗ Thermal object records (→ thermal_objects table)
--   ✗ AI model outputs (→ source_attributions, anomaly_results)
--
-- RAG tables are completely isolated from the operational
-- satellite observation pipeline.
--
-- Embedding dimension:
--   Default: 1536 (OpenAI text-embedding-3-small / ada-002)
--   To change: set PGVECTOR_EMBEDDING_DIMENSION in .env BEFORE
--   running this migration, then manually replace 1536 in the
--   rag_chunks.embedding column definition below.
--   WARNING: changing dimension after data insertion requires
--   dropping and recreating the column + index + re-embedding.
-- =============================================================

-- =============================================================
-- TABLE: rag_documents
-- =============================================================
-- Purpose:
--   Full source documents forming the HEATWATCH knowledge base.
--   Chunked into rag_chunks for embedding and retrieval.
-- =============================================================

CREATE TABLE rag_documents (
    id               UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),

    title            TEXT        NOT NULL,
    source           TEXT        NOT NULL,   -- URL, filename, or data origin name

    -- Document type classification
    source_type      TEXT        NOT NULL
                       CHECK (source_type IN (
                           'SCIENTIFIC_PAPER',
                           'REGULATORY_DOCUMENT',
                           'TECHNICAL_REPORT',
                           'CLASSIFICATION_POLICY',
                           'EVIDENCE_POLICY',
                           'MODEL_DOCUMENTATION',
                           'VERIFIED_CASE_SUMMARY',
                           'SATELLITE_PRODUCT_GUIDE',
                           'OTHER'
                       )),
    source_reference TEXT,        -- DOI, regulatory ID, internal reference

    -- Full document text (stored for re-chunking if strategy changes)
    content          TEXT        NOT NULL,

    -- Flexible metadata (author, year, tags, language, etc.)
    metadata         JSONB,

    -- Version tracking for re-ingestion
    version          TEXT        NOT NULL DEFAULT '1',

    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE rag_documents IS
    'RAG knowledge base documents. '
    'Isolated from satellite observation tables. '
    'Full document text stored for re-chunking without requiring re-fetch.';

CREATE TRIGGER trg_rag_documents_updated_at
    BEFORE UPDATE ON rag_documents
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();


-- =============================================================
-- TABLE: rag_chunks
-- =============================================================
-- Purpose:
--   Text chunks of rag_documents with pgvector embeddings.
--   Retrieved by the supervisor pipeline using ANN similarity.
--
-- Embedding dimension: 1536
--   ► Change this value if using a different embedding model.
--   ► Document the change in the migration changelog.
--   ► Rebuild all embeddings and the vector index after any change.
-- =============================================================

CREATE TABLE rag_chunks (
    id            UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id   UUID        NOT NULL
                    REFERENCES rag_documents(id) ON DELETE CASCADE,

    -- Position within parent document
    chunk_index   INTEGER     NOT NULL
                    CHECK (chunk_index >= 0),

    -- Chunk content
    chunk_text    TEXT        NOT NULL,

    -- pgvector embedding
    -- Dimension: 1536 — change before first data insertion if required
    -- See: database/.env.example → PGVECTOR_EMBEDDING_DIMENSION
    embedding     vector(1536) NOT NULL,

    -- Flexible metadata (embedding model name, chunking strategy, etc.)
    metadata      JSONB,

    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Prevent duplicate chunks per document
    CONSTRAINT uq_rag_chunk_doc_index UNIQUE (document_id, chunk_index)
);

COMMENT ON TABLE rag_chunks IS
    'Chunked text segments of RAG documents with pgvector embeddings. '
    'Embedding dimension: 1536 (OpenAI default). '
    'ON DELETE CASCADE: removing a document removes all its chunks.';

COMMENT ON COLUMN rag_chunks.embedding IS
    'pgvector embedding of chunk_text. '
    'Dimension = 1536 (default). Must match the embedding model output dimension. '
    'To change: drop column, recreate with new dimension, re-embed all chunks.';


DO $$
BEGIN
  RAISE NOTICE 'Migration 006: RAG tables created (rag_documents, rag_chunks).';
END $$;
