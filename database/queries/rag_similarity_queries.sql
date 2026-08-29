-- =============================================================
-- HEATWATCH — RAG Vector Similarity Query Examples
-- database/queries/rag_similarity_queries.sql
-- =============================================================
-- These queries use pgvector's cosine distance operator <=>
-- (1 - cosine_similarity). Lower value = more similar.
--
-- In application code, replace the placeholder literal vector
-- with the actual embedding vector produced by your embedding
-- model (e.g. OpenAI, Google Gecko, Sentence Transformers).
--
-- The placeholder below uses a 5-dimension vector for readability.
-- Replace with your actual embedding dimension (default: 1536).
-- =============================================================

-- =============================================================
-- Q1: Top-5 most semantically similar chunks to a query
-- (Basic cosine similarity — no metadata filter)
-- =============================================================
-- In application code, bind :query_embedding as a vector parameter.
-- Example in psql: \set query_embedding '[0.01,0.02,...1536 values...]'

SELECT
    rc.id            AS chunk_id,
    rd.title         AS document_title,
    rd.source_type,
    rd.source,
    rc.chunk_index,
    rc.chunk_text,
    1 - (rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector)
                     AS cosine_similarity
FROM rag_chunks rc
JOIN rag_documents rd ON rd.id = rc.document_id
ORDER BY rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector
LIMIT 5;


-- =============================================================
-- Q2: Similarity search filtered by document source_type
-- (Pre-filter before ANN — reduces search space)
-- =============================================================
SELECT
    rc.id            AS chunk_id,
    rd.title,
    rd.source_type,
    rc.chunk_index,
    rc.chunk_text,
    1 - (rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector)
                     AS cosine_similarity
FROM rag_chunks rc
JOIN rag_documents rd ON rd.id = rc.document_id
WHERE rd.source_type IN (
    'SCIENTIFIC_PAPER',
    'CLASSIFICATION_POLICY',
    'EVIDENCE_POLICY'
)
ORDER BY rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector
LIMIT 5;


-- =============================================================
-- Q3: Retrieve full document + chunk text for top matches
-- (Useful for context window assembly in supervisor LLM call)
-- =============================================================
SELECT
    rd.id            AS document_id,
    rd.title,
    rd.source,
    rd.source_type,
    rd.version,
    rc.id            AS chunk_id,
    rc.chunk_index,
    rc.chunk_text,
    rc.metadata      AS chunk_metadata,
    1 - (rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector)
                     AS cosine_similarity
FROM rag_chunks rc
JOIN rag_documents rd ON rd.id = rc.document_id
ORDER BY rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector
LIMIT 10;


-- =============================================================
-- Q4: Chunk metadata filtering + similarity
-- (Filter on chunk-level metadata tags before ANN)
-- =============================================================
SELECT
    rc.id,
    rc.chunk_text,
    rc.metadata,
    1 - (rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector)
                    AS cosine_similarity
FROM rag_chunks rc
WHERE rc.metadata @> '{"topic": "gas_flare"}'   -- JSONB containment filter
ORDER BY rc.embedding <=> '[0.01,0.02,0.03,0.04,0.05]'::vector
LIMIT 5;


-- =============================================================
-- Q5: Insert a RAG document and its first chunk
-- (Full insertion example for application code reference)
-- =============================================================
-- Step 1: Insert the document
INSERT INTO rag_documents (title, source, source_type, content, version)
VALUES (
    'Industrial Flaring Classification Guidelines',
    'https://example.org/flaring-guide-2024.pdf',
    'CLASSIFICATION_POLICY',
    'Full document text here...',
    '1'
)
RETURNING id;

-- Step 2: Insert a chunk with its embedding
-- Replace the vector literal with real embedding output.
INSERT INTO rag_chunks (document_id, chunk_index, chunk_text, embedding, metadata)
VALUES (
    'DOCUMENT_UUID_FROM_STEP_1'::uuid,
    0,
    'Industrial flaring is a controlled combustion process...',
    '[0.01,0.02,0.03,0.04,0.05]'::vector,  -- Replace with real 1536-dim vector
    '{"topic": "gas_flare", "embedding_model": "text-embedding-3-small"}'
);


-- =============================================================
-- Q6: List all RAG documents with chunk counts
-- =============================================================
SELECT
    rd.id,
    rd.title,
    rd.source_type,
    rd.version,
    rd.created_at,
    COUNT(rc.id)    AS chunk_count
FROM rag_documents rd
LEFT JOIN rag_chunks rc ON rc.document_id = rd.id
GROUP BY rd.id, rd.title, rd.source_type, rd.version, rd.created_at
ORDER BY rd.created_at DESC;
