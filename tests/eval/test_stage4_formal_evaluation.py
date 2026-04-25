"""Stage 4 formal evaluation metrics and comparison tests."""

from __future__ import annotations

from pathlib import Path

from app.rag.evaluation import (
    build_assessment_table,
    compare_rerankers,
    compare_retrieval_quality,
    deepeval_available,
    evaluate_rbac_scenarios,
    evaluate_routing_modes,
    evaluate_zero_hallucination_scenarios,
    summarize_evaluations,
)
from app.rag.retrieval import FusionResult, rerank

ROOT = Path(__file__).resolve().parent.parent.parent


class _ReverseReranker:
    model_id = "fake-cohere-rerank"

    def rerank(self, query, candidates):
        return list(reversed(candidates))


def test_zero_hallucination_scenarios_produce_formal_metrics(rag_service, users):
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    assert rows
    summary = summarize_evaluations(rows, mode="deterministic")
    assert summary.citation_completeness >= 0.8
    assert summary.citation_accuracy == 1.0
    assert summary.rbac_leakage_count == 0


def test_rbac_scenarios_have_zero_restricted_citation_leakage(rag_service, users):
    rows = evaluate_rbac_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "security" / "rbac_llm_scenarios.json",
    )
    assert rows
    assert sum(row.rbac_leakage_count for row in rows) == 0
    assert sum(row.prompt_injection_success_count for row in rows) == 0


def test_assessment_table_contains_required_final_metrics(rag_service, users):
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    table = build_assessment_table(summarize_evaluations(rows, mode="deterministic"))
    metrics = {row["metric"] for row in table}
    assert {
        "faithfulness",
        "citation_completeness",
        "citation_accuracy",
        "abstention_correctness",
        "rbac_leakage_count",
        "ttft_p95_seconds",
        "estimated_cost_per_1000_queries",
    }.issubset(metrics)


def test_compare_retrieval_quality_reports_overlap(backend, embedder, users):
    comparison = compare_retrieval_quality(
        query="Can a taxpayer deduct home office expenses?",
        user=users["u_helpdesk_01"],
        baseline_backend=backend,
        baseline_embedder=embedder,
        candidate_backend=backend,
        candidate_embedder=embedder,
    )
    assert comparison["jaccard_overlap"] == 1.0
    assert comparison["candidate_has_complete_citations"] is True


def test_compare_rerankers_reports_order_change(corpus_chunks):
    candidates = [FusionResult(chunk, rrf_score=1.0 / (i + 1)) for i, chunk in enumerate(corpus_chunks[:3])]
    comparison = compare_rerankers(
        query="home office deduction",
        candidates=candidates,
        baseline_reranker=lambda query, rows: rerank(query, rows),
        candidate_reranker=_ReverseReranker(),
    )
    assert comparison["baseline_order"]
    assert comparison["candidate_order"] == list(reversed(comparison["baseline_order"]))


def test_routing_mode_evaluation_summarizes_each_mode(rag_service, users):
    summaries = evaluate_routing_modes(
        service_factory_by_mode={"deterministic": lambda: rag_service, "haiku": lambda: rag_service},
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    assert set(summaries) == {"deterministic", "haiku"}
    assert all(summary.scenario_count > 0 for summary in summaries.values())


def test_deepeval_dependency_check_returns_boolean():
    assert isinstance(deepeval_available(), bool)
