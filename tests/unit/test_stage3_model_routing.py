"""Stage 3 model-routing and optional Bedrock wiring tests."""

from __future__ import annotations

from pathlib import Path

from app.rag.generation import GeneratedAnswer
from app.rag.model_routing import ModelRouter, classify_query_risk, evaluate_service_mode
from app.rag.models import Citation
from app.rag.service import RagService, build_service_from_paths

ROOT = Path(__file__).resolve().parent.parent.parent


def test_model_router_keeps_deterministic_as_default(users):
    decision = ModelRouter().route("Can a taxpayer deduct home office expenses?", users["u_helpdesk_01"])
    assert decision.mode == "deterministic"
    assert decision.model_id == "deterministic-extractive-v1"


def test_model_router_escalates_high_risk_query_from_haiku_to_sonnet(users):
    decision = ModelRouter().route(
        "What is the legal interpretation after ECLI:NL:HR:2023:123?",
        users["u_helpdesk_01"],
        mode="haiku",
    )
    assert decision.mode == "sonnet"
    assert decision.risk_level == "high"


def test_model_router_allows_haiku_for_low_risk_helpdesk_summary(users):
    decision = ModelRouter().route("Summarize documentation duties for helpdesk.", users["u_helpdesk_01"], mode="haiku")
    assert decision.mode == "haiku"
    assert decision.risk_level == "low"


def test_classify_query_risk_marks_fiod_and_numeric_exact_queries_high(users):
    assert classify_query_risk("What fraud indicators apply?", users["u_helpdesk_01"]) == "high"
    assert classify_query_risk("What percentage is deductible?", users["u_helpdesk_01"]) == "high"
    assert classify_query_risk("Summarize documentation duties", users["u_fiod_01"]) == "high"


def test_graph_uses_injected_answer_composer(corpus_chunks, backend, embedder, users):
    calls = []

    def composer(query, context):
        calls.append((query, context))
        chunk = context[0]
        citation = Citation(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_name=chunk.document_name,
            article=chunk.article,
            paragraph=chunk.paragraph,
        )
        return GeneratedAnswer(text=f"Injected answer {citation.format()}", citations=[citation], abstained=False)

    service = RagService(chunks=corpus_chunks, backend=backend, embedder=embedder, answer_composer=composer)
    result = service.ask(users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?")
    assert calls
    assert not result.abstained
    assert result.answer.startswith("Injected answer")


def test_build_service_from_paths_keeps_bedrock_flags_off_by_default(monkeypatch):
    monkeypatch.delenv("BEDROCK_EMBEDDINGS_ENABLED", raising=False)
    monkeypatch.delenv("BEDROCK_RERANK_ENABLED", raising=False)
    monkeypatch.delenv("BEDROCK_GENERATION_ENABLED", raising=False)
    service, users = build_service_from_paths(
        manifest_path=ROOT / "sample_corpus" / "manifest.json",
        users_path=ROOT / "sample_requests" / "users.json",
    )
    result = service.ask(users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?")
    assert not result.abstained
    assert service.backend is not None


def test_evaluate_service_mode_reports_citation_and_rbac_metrics(rag_service, users):
    evaluation = evaluate_service_mode(
        service_factory=lambda: rag_service,
        user=users["u_helpdesk_01"],
        query="Can a taxpayer deduct home office expenses?",
        mode="deterministic",
    )
    assert evaluation.passed
    assert evaluation.citation_completeness == 1.0
    assert evaluation.citation_accuracy == 1.0
    assert evaluation.rbac_leakage_count == 0
