# Module 1: Ingestion & Knowledge Structuring

## Objective

Design ingestion for legal texts, case law, policies, and e-learning content without destroying hierarchy, citation context, access metadata, or version history.

## Design

- Parse documents by source type rather than applying a generic recursive splitter first.
- For legislation, preserve hierarchy: chapter -> section -> article -> paragraph.
- For case law, preserve ECLI, facts, legal question, reasoning, holding, and paragraph numbers.
- For policy/e-learning, preserve section headings, paragraph numbers, classification, and allowed roles.
- Generate chunks at article/paragraph or reasoning-paragraph boundaries; only use token splitting inside an already identified legal unit when the unit is too large.
- Attach citation metadata to every chunk before embedding: document name, document id, article/section, paragraph, section path, effective dates, version, classification level, and allowed roles.
- Keep lineage: raw document path -> parsed legal units -> chunk ids -> embedding/index ids.

## Configs

- Preferred vector database: OpenSearch for hybrid BM25 + vector retrieval, DLS/query-time RBAC filters, and operational fit.
- HNSW starting point: `m=32`, `ef_construction=256`, runtime `ef_search=128`.
- Initial retrieval defaults: lexical top-k `50`, vector top-k `50`, fused candidates `60-80`, rerank max `60`, final context `5-8` chunks.
- Chunking target: one legal paragraph per chunk where possible; max `700-1,000` tokens for long paragraphs; overlap `0-80` tokens only inside long legal units.
- Embedding batch size: start `64-256` depending on provider limits and memory.
- Memory controls: bounded top-k, bounded `ef_search`, shard sizing benchmarks, vector quantization after recall tests, bulk indexing, circuit breakers, and no unbounded reranking.
- OpenSearch expected config fixture: [`tests/integration/opensearch_index_config_expected.json`](../tests/integration/opensearch_index_config_expected.json).

## Pseudo-code

```python
def ingest_document(path):
    raw = load_markdown_or_pdf(path)
    header = parse_front_matter(raw)
    legal_units = parse_by_source_type(raw, header["source_type"])

    chunks = []
    for unit in legal_units:
        for paragraph in split_by_legal_paragraph(unit):
            chunk = {
                "chunk_id": stable_hash(header["document_id"], unit.path, paragraph.number),
                "document_id": header["document_id"],
                "document_name": header["document_name"],
                "source_type": header["source_type"],
                "text": paragraph.text,
                "article": unit.article_or_section,
                "paragraph": paragraph.number,
                "section_path": unit.section_path,
                "effective_from": header.get("effective_from"),
                "effective_to": header.get("effective_to"),
                "version": header.get("version"),
                "classification_level": header["classification_level"],
                "allowed_roles": header["allowed_roles"],
            }
            chunk["embedding"] = embed(chunk["text"])
            chunks.append(chunk)

    bulk_index_opensearch(chunks)
```

## Tests

- Unit chunking fixtures: [`tests/unit/ingestion_chunking_cases.json`](../tests/unit/ingestion_chunking_cases.json).
- Sample corpus: [`sample_corpus/README.md`](../sample_corpus/README.md).
- Test that Article 3.12 Paragraph 2 produces a chunk with `article = "3.12"`, `paragraph = "2"`, and a full `section_path`.
- Test historical version metadata: 2022 law must include `effective_to = "2022-12-31"` and must not be used for later tax years without a transition rule.
- Test case-law chunking keeps ECLI and paragraph numbers.
- Test restricted FIOD chunks preserve `classification_level = 5` and `allowed_roles = ["fiod_investigator"]` before indexing.
- Test OpenSearch mapping contains `knn_vector`, HNSW settings, citation fields, version fields, and RBAC fields.

## Tradeoffs

- Paragraph-level chunks maximize citation precision but may reduce semantic context; include section path and neighboring legal hierarchy in metadata to recover context.
- Large chunks improve context but weaken exact citation guarantees.
- Quantization reduces memory and OOM risk but must be benchmarked for recall loss.
- More shards reduce per-shard memory pressure but can increase coordination latency; benchmark with realistic 20M+ chunk distribution.
- Higher `ef_search` improves recall but increases memory and latency; start at `128` and tune with p95/p99 latency and recall tests.

