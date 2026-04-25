"""Legal-aware chunking and metadata preservation tests.

Drives the fixtures in tests/unit/ingestion_chunking_cases.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
CASES = json.loads((ROOT / "tests" / "unit" / "ingestion_chunking_cases.json").read_text())
REQUIRED_FIELDS = CASES["required_chunk_metadata"]


CITATION_CRITICAL_FIELDS = {
    "chunk_id",
    "document_id",
    "document_name",
    "source_type",
    "article",
    "paragraph",
    "section_path",
    "classification_level",
    "allowed_roles",
}

# effective_from / effective_to / version are only required when the source
# document's front matter declares them (all legislation; policy/e-learning
# may omit them per the sample corpus spec).
VERSIONED_SOURCE_TYPES = {"legislation"}


def test_every_chunk_has_citation_critical_metadata(corpus_chunks):
    missing: list[tuple[str, str]] = []
    for chunk in corpus_chunks:
        for field in CITATION_CRITICAL_FIELDS:
            value = getattr(chunk, field, None)
            if value is None or value == "":
                missing.append((chunk.chunk_id, field))
    assert not missing, f"chunks missing citation metadata: {missing}"


def test_legislation_chunks_carry_versioned_fields(corpus_chunks):
    legislation = [c for c in corpus_chunks if c.source_type in VERSIONED_SOURCE_TYPES]
    assert legislation
    for chunk in legislation:
        assert chunk.effective_from
        assert chunk.version


def test_legislation_article_paragraph_extracted(corpus_chunks):
    expected = {("3.12", "1"), ("3.12", "2"), ("3.12", "3"), ("3.13", "1"), ("3.13", "2")}
    seen = {
        (c.article, c.paragraph)
        for c in corpus_chunks
        if c.document_id == "DOC-LEG-001"
    }
    assert expected.issubset(seen)


def test_article_3_12_paragraph_2_has_section_path(corpus_chunks):
    target = next(
        c
        for c in corpus_chunks
        if c.document_id == "DOC-LEG-001" and c.article == "3.12" and c.paragraph == "2"
    )
    assert target.article == "3.12"
    assert target.paragraph == "2"
    joined = " ".join(target.section_path)
    assert "Chapter 3" in joined
    assert "Section 3.1" in joined
    assert "Article 3.12" in joined
    assert "contemporaneous records" in target.text


def test_historical_effective_dates_preserved(corpus_chunks):
    chunks = [c for c in corpus_chunks if c.document_id == "DOC-LEG-2022-001"]
    assert chunks
    for chunk in chunks:
        assert chunk.effective_from == "2022-01-01"
        assert chunk.effective_to == "2022-12-31"
        assert chunk.version == "2022-historical"


def test_case_law_preserves_ecli_sections_and_paragraphs(corpus_chunks):
    case_chunks = [c for c in corpus_chunks if c.document_id == "DOC-CASE-001"]
    assert case_chunks
    assert all(c.ecli == "ECLI:NL:HR:2023:123" for c in case_chunks)
    sections = {c.article for c in case_chunks}
    assert {"Facts", "Legal Question", "Reasoning", "Holding"}.issubset(sections)
    paragraphs = {c.paragraph for c in case_chunks}
    assert {"10", "11", "14", "15", "18"}.issubset(paragraphs)


def test_restricted_fiod_metadata_preserved(corpus_chunks):
    fiod = [c for c in corpus_chunks if c.document_id == "DOC-FIOD-001"]
    assert fiod
    for chunk in fiod:
        assert chunk.classification_level == 5
        assert chunk.allowed_roles == ["fiod_investigator"]
        assert chunk.case_scope == "FIOD-2024-001"
        assert "FIOD" in chunk.classification_tags
        assert "fraud_investigation" in chunk.classification_tags


def test_chunk_ids_are_stable_and_unique(corpus_chunks):
    ids = [c.chunk_id for c in corpus_chunks]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("document_id", ["DOC-LEG-001", "DOC-LEG-2022-001"])
def test_paragraph_order_is_sequential(corpus_chunks, document_id):
    chunks = [c for c in corpus_chunks if c.document_id == document_id]
    for article in {c.article for c in chunks}:
        nums = [int(c.paragraph) for c in chunks if c.article == article]
        assert nums == sorted(nums)
