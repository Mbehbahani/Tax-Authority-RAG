"""Legal-aware ingestion pipeline.

Parses the synthetic sample corpus by source_type (legislation, case_law,
internal_policy, elearning) and emits chunks whose metadata preserves legal
hierarchy, citation anchors, versioning, and RBAC classification exactly as
required by Module 1 of the assessment.

No external parsers are used so the pipeline can run locally without heavy
dependencies. Tokenisation for "too large" paragraphs is word-based as a
conservative stand-in; for production these would be replaced by a real
tokenizer and a real corpus loader from S3.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .models import Chunk

FRONT_MATTER_RE = re.compile(r"^---\s*\n(?P<yaml>.*?)\n---\s*\n", re.DOTALL)
ARTICLE_HEADING_RE = re.compile(
    r"^####\s+Article\s+(?P<article>[0-9A-Za-z.\-]+)\s*(?:—|-|–)?\s*(?P<title>.*)$",
    re.MULTILINE,
)
SECTION_HEADING_RE = re.compile(r"^###\s+(?P<section>.+)$", re.MULTILINE)
CHAPTER_HEADING_RE = re.compile(r"^##\s+(?P<chapter>.+)$", re.MULTILINE)
CASE_SECTION_RE = re.compile(r"^##\s+(?P<section>.+)$", re.MULTILINE)
PARAGRAPH_RE = re.compile(r"^Paragraph\s+(?P<num>\d+)\.\s+(?P<text>.+?)(?=^\s*(?:Paragraph\s+\d+\.|#|$))",
                          re.MULTILINE | re.DOTALL)

# Classification tag heuristics. Internal policy documents that carry a FIOD
# case_scope or are ONLY accessible to fiod_investigator are tagged with
# FIOD/fraud_investigation so query-time must_not filters can hide them.
FIOD_ONLY_ROLES = {"fiod_investigator"}


@dataclass
class _DocumentHeader:
    document_id: str
    document_name: str
    source_type: str
    classification_level: int
    allowed_roles: list[str]
    effective_from: str | None
    effective_to: str | None
    version: str | None
    ecli: str | None
    case_scope: str | None
    classification_tags: list[str]


def _parse_front_matter(raw: str) -> tuple[dict[str, Any], str]:
    match = FRONT_MATTER_RE.match(raw)
    if not match:
        raise ValueError("document is missing YAML front matter")
    yaml_block = match.group("yaml")
    body = raw[match.end():]
    meta: dict[str, Any] = {}
    for line in yaml_block.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = _coerce_yaml_value(value.strip())
    return meta, body


def _coerce_yaml_value(value: str) -> Any:
    if value.lower() in {"null", "none", ""}:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(p.strip()) for p in inner.split(",")]
    return _strip_quotes(value)


def _strip_quotes(value: str) -> Any:
    if len(value) >= 2 and value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    if value.isdigit():
        return int(value)
    return value


def _build_header(meta: dict[str, Any]) -> _DocumentHeader:
    allowed_roles = meta.get("allowed_roles") or []
    if isinstance(allowed_roles, str):
        allowed_roles = [allowed_roles]
    classification_tags: list[str] = []
    case_scope = meta.get("case_scope")
    if case_scope or set(allowed_roles) == FIOD_ONLY_ROLES:
        classification_tags.extend(["FIOD", "fraud_investigation"])
    return _DocumentHeader(
        document_id=str(meta["document_id"]),
        document_name=str(meta["document_name"]),
        source_type=str(meta["source_type"]),
        classification_level=int(meta.get("classification_level", 1)),
        allowed_roles=list(allowed_roles),
        effective_from=meta.get("effective_from"),
        effective_to=meta.get("effective_to"),
        version=meta.get("version"),
        ecli=meta.get("ecli"),
        case_scope=case_scope,
        classification_tags=classification_tags,
    )


def _stable_chunk_id(*parts: str) -> str:
    joined = "::".join(parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:20]


def _iter_paragraphs(block: str) -> Iterable[tuple[str, str]]:
    for match in PARAGRAPH_RE.finditer(block):
        num = match.group("num")
        text = match.group("text").strip()
        text = re.sub(r"\s+", " ", text)
        yield num, text


def _chunk_legislation(header: _DocumentHeader, body: str) -> list[Chunk]:
    """Chunk legislation by chapter -> section -> article -> paragraph."""

    chunks: list[Chunk] = []
    chapter_title = _first_match(CHAPTER_HEADING_RE, body, "chapter") or ""
    sections = _split_on_heading(body, SECTION_HEADING_RE, key="section")
    if not sections:
        sections = [("", body)]

    for section_title, section_body in sections:
        articles = _split_on_article(section_body)
        for article_number, article_title, article_body in articles:
            section_path = [
                s for s in (chapter_title, section_title, f"Article {article_number}") if s
            ]
            for paragraph_num, paragraph_text in _iter_paragraphs(article_body):
                chunk = Chunk(
                    chunk_id=_stable_chunk_id(
                        header.document_id, article_number, paragraph_num
                    ),
                    document_id=header.document_id,
                    document_name=header.document_name,
                    source_type=header.source_type,
                    text=paragraph_text,
                    article=article_number,
                    paragraph=paragraph_num,
                    section_path=section_path,
                    effective_from=header.effective_from,
                    effective_to=header.effective_to,
                    version=header.version,
                    classification_level=header.classification_level,
                    allowed_roles=list(header.allowed_roles),
                    classification_tags=list(header.classification_tags),
                    case_scope=header.case_scope,
                    ecli=header.ecli,
                )
                chunks.append(chunk)
    return chunks


def _chunk_case_law(header: _DocumentHeader, body: str) -> list[Chunk]:
    """Chunk case-law by section (Facts / Legal Question / Reasoning / Holding)."""

    chunks: list[Chunk] = []
    sections = _split_on_heading(body, CASE_SECTION_RE, key="section")
    if not sections:
        sections = [("Body", body)]
    for section_title, section_body in sections:
        for paragraph_num, paragraph_text in _iter_paragraphs(section_body):
            chunk = Chunk(
                chunk_id=_stable_chunk_id(
                    header.document_id, section_title, paragraph_num
                ),
                document_id=header.document_id,
                document_name=header.document_name,
                source_type=header.source_type,
                text=paragraph_text,
                # For case law we store the section label as the "article"
                # anchor so citations remain uniform across source types.
                article=section_title,
                paragraph=paragraph_num,
                section_path=[section_title],
                effective_from=header.effective_from,
                effective_to=header.effective_to,
                version=header.version,
                classification_level=header.classification_level,
                allowed_roles=list(header.allowed_roles),
                classification_tags=list(header.classification_tags),
                case_scope=header.case_scope,
                ecli=header.ecli,
            )
            chunks.append(chunk)
    return chunks


def _chunk_policy_or_elearning(header: _DocumentHeader, body: str) -> list[Chunk]:
    """Chunk policy/e-learning by 'Section N' or 'Module N' sub-headings.

    The synthetic policy/e-learning documents use ``##`` for the Section/Module
    label. We try the ``##`` level first and fall back to ``###`` so either
    convention parses correctly.
    """

    chunks: list[Chunk] = []
    sections = _split_on_heading(body, CASE_SECTION_RE, key="section")
    if not sections:
        sections = _split_on_heading(body, SECTION_HEADING_RE, key="section")
    if not sections:
        sections = [("Body", body)]
    for section_title, section_body in sections:
        article_label = _article_label_from_section(section_title)
        for paragraph_num, paragraph_text in _iter_paragraphs(section_body):
            chunk = Chunk(
                chunk_id=_stable_chunk_id(
                    header.document_id, section_title, paragraph_num
                ),
                document_id=header.document_id,
                document_name=header.document_name,
                source_type=header.source_type,
                text=paragraph_text,
                article=article_label,
                paragraph=paragraph_num,
                section_path=[section_title],
                effective_from=header.effective_from,
                effective_to=header.effective_to,
                version=header.version,
                classification_level=header.classification_level,
                allowed_roles=list(header.allowed_roles),
                classification_tags=list(header.classification_tags),
                case_scope=header.case_scope,
                ecli=header.ecli,
            )
            chunks.append(chunk)
    return chunks


def _article_label_from_section(section_title: str) -> str:
    """Pull a stable 'Section N' / 'Module N' label from a heading.

    Example: 'Section 2 — Standard Helpdesk Response' -> 'Section 2'.
    """

    cleaned = section_title.strip()
    match = re.match(r"^(Section|Module|Chapter)\s+[0-9A-Za-z.\-]+", cleaned)
    if match:
        return match.group(0)
    return cleaned.split("—", 1)[0].strip() or cleaned


def _first_match(pattern: re.Pattern[str], body: str, key: str) -> str | None:
    match = pattern.search(body)
    return match.group(key).strip() if match else None


def _split_on_heading(body: str, pattern: re.Pattern[str], *, key: str) -> list[tuple[str, str]]:
    """Split body into (heading, content) pairs at ## or ### boundaries."""

    matches = list(pattern.finditer(body))
    if not matches:
        return []
    sections: list[tuple[str, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        sections.append((match.group(key).strip(), body[start:end]))
    return sections


def _split_on_article(body: str) -> list[tuple[str, str, str]]:
    matches = list(ARTICLE_HEADING_RE.finditer(body))
    if not matches:
        return []
    articles: list[tuple[str, str, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        articles.append(
            (match.group("article").strip(), match.group("title").strip(), body[start:end])
        )
    return articles


def parse_document(path: Path) -> list[Chunk]:
    """Parse a single markdown file into legal-aware chunks."""

    raw = path.read_text(encoding="utf-8")
    meta, body = _parse_front_matter(raw)
    header = _build_header(meta)

    if header.source_type == "legislation":
        return _chunk_legislation(header, body)
    if header.source_type == "case_law":
        return _chunk_case_law(header, body)
    if header.source_type in {"internal_policy", "elearning"}:
        return _chunk_policy_or_elearning(header, body)
    raise ValueError(f"unsupported source_type: {header.source_type}")


def load_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return list(data.get("documents", []))


def ingest_corpus(manifest_path: Path, root: Path | None = None) -> list[Chunk]:
    """Load every document listed in manifest.json and return all chunks."""

    manifest_path = manifest_path.resolve()
    base = root.resolve() if root else manifest_path.parent.parent
    chunks: list[Chunk] = []
    for entry in load_manifest(manifest_path):
        doc_path = (base / entry["path"]).resolve()
        chunks.extend(parse_document(doc_path))
    return chunks
