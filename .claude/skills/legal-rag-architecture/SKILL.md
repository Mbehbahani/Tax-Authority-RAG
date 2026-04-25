---
name: legal-rag-architecture
description: Guidance for legal RAG ingestion, hierarchy-preserving chunking, metadata, citations, versioning, and access-control metadata.
---

# Skill: Legal RAG Architecture

Use this skill when designing legal-document ingestion, chunking, metadata, and citation behavior.

## Guidance

- Preserve legal hierarchy: code, title, chapter, section, article, paragraph, clause.
- Chunk legislation at article/paragraph boundaries; avoid splitting normative statements.
- Chunk case law by procedural metadata, facts, legal question, reasoning, holding, and citations.
- Include citation metadata on every chunk: document name, document id, version, article, paragraph, page/section if available.
- Track effective dates, expiry dates, supersession, and historical/current status.
- Track document versions and lineage from raw source to normalized text to chunk.
- Include `classification`, `allowed_roles`, `jurisdiction`, `source_type`, and `legal_domain`.
- Ensure retrieval and generation can only use chunks authorized for the user.

## Stage 1 Implementation Best Practices

- Treat source-specific parsers as first-class components; do not start with generic recursive splitting.
- Make chunk ids deterministic from document id, version, section path, article, and paragraph.
- Store citation metadata before embedding/indexing so downstream retrieval cannot lose citation context.
- Preserve `effective_from` and `effective_to` for historical/current law selection.
- Preserve `classification_level`, `classification_tags`, `allowed_roles`, `case_scope`, and `need_to_know_groups` for retrieval filters.
- Add validation that rejects chunks missing required citation or authorization metadata.
- Keep sample corpus synthetic and clearly marked as not real legal advice.

