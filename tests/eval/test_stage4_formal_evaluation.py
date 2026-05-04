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
    evaluate_single_scenario,
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


# ---------------------------------------------------------------------------
# New: wired performance + IR metrics
# ---------------------------------------------------------------------------


def test_summary_has_latency_percentiles(rag_service, users):
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    summary = summarize_evaluations(rows, mode="deterministic")
    # All three percentile fields must be present and non-negative.
    assert summary.latency_p50_seconds >= 0.0
    assert summary.latency_p95_seconds >= 0.0
    assert summary.latency_p99_seconds >= 0.0
    # p50 <= p95 <= p99 for any non-empty latency sample.
    assert summary.latency_p50_seconds <= summary.latency_p95_seconds
    assert summary.latency_p95_seconds <= summary.latency_p99_seconds
    # ttft_p95_seconds and latency_p95_seconds are the same measurement in
    # this local PoC (no streaming; TTFT == end-to-end latency).
    assert summary.ttft_p95_seconds == summary.latency_p95_seconds


def test_summary_has_cache_hit_rate(rag_service, users):
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    summary = summarize_evaluations(rows, mode="deterministic")
    assert 0.0 <= summary.cache_hit_rate <= 1.0


def test_ir_metrics_are_none_when_no_gold_labels(rag_service, users):
    # The bundled zero_hallucination_scenarios.json has no relevant_document_ids,
    # so IR ranking metrics must be None rather than a guessed value.
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    summary = summarize_evaluations(rows, mode="deterministic")
    assert summary.mean_precision_at_k is None
    assert summary.mean_recall_at_k is None
    assert summary.mean_mrr_at_k is None
    assert summary.mean_ndcg_at_k is None
    # IR rows must NOT appear in the assessment table when metrics are None.
    table_metrics = {row["metric"] for row in build_assessment_table(summary)}
    assert "mean_precision_at_k" not in table_metrics
    assert "mean_recall_at_k" not in table_metrics


def test_ir_metrics_computed_when_gold_labels_provided(rag_service, users):
    # Supply a relevant_document_ids list directly via evaluate_single_scenario.
    row = evaluate_single_scenario(
        service_factory=lambda: rag_service,
        users=users,
        scenario_id="manual_gold_test",
        suite="test",
        query="Can a taxpayer deduct home office expenses?",
        user_id="u_helpdesk_01",
        mode="deterministic",
        expected_behavior="answer_with_exact_citations_per_claim",
        must_not_retrieve=[],
        relevant_document_ids=["DOC-LEG-001", "DOC-POL-001"],
        k=5,
    )
    # Metrics must be floats in [0, 1] when gold labels exist.
    assert row.scenario_precision_at_k is not None
    assert row.scenario_recall_at_k is not None
    assert row.scenario_mrr_at_k is not None
    assert row.scenario_ndcg_at_k is not None
    assert 0.0 <= row.scenario_precision_at_k <= 1.0
    assert 0.0 <= row.scenario_recall_at_k <= 1.0
    assert 0.0 <= row.scenario_mrr_at_k <= 1.0
    assert 0.0 <= row.scenario_ndcg_at_k <= 1.0


def test_ir_metrics_appear_in_table_when_gold_labels_present(rag_service, users):
    row = evaluate_single_scenario(
        service_factory=lambda: rag_service,
        users=users,
        scenario_id="table_gold_test",
        suite="test",
        query="Can a taxpayer deduct home office expenses?",
        user_id="u_helpdesk_01",
        mode="deterministic",
        expected_behavior="answer_with_exact_citations_per_claim",
        must_not_retrieve=[],
        relevant_document_ids=["DOC-LEG-001", "DOC-POL-001"],
    )
    summary = summarize_evaluations([row], mode="deterministic")
    table_metrics = {r["metric"] for r in build_assessment_table(summary)}
    assert "mean_precision_at_k" in table_metrics
    assert "mean_recall_at_k" in table_metrics
    assert "mean_mrr_at_k" in table_metrics
    assert "mean_ndcg_at_k" in table_metrics


def test_assessment_table_contains_new_latency_and_cache_rows(rag_service, users):
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    table = build_assessment_table(summarize_evaluations(rows, mode="deterministic"))
    metrics = {row["metric"] for row in table}
    assert {"latency_p50_seconds", "latency_p95_seconds", "latency_p99_seconds", "cache_hit_rate"}.issubset(metrics)


def test_scenario_cache_hit_field_is_bool(rag_service, users):
    rows = evaluate_zero_hallucination_scenarios(
        service_factory=lambda: rag_service,
        users=users,
        scenarios_path=ROOT / "tests" / "eval" / "zero_hallucination_scenarios.json",
    )
    for row in rows:
        assert isinstance(row.cache_hit, bool)


def test_summarize_empty_rows_returns_zero_defaults():
    summary = summarize_evaluations([], mode="deterministic")
    assert summary.scenario_count == 0
    assert summary.latency_p50_seconds == 0.0
    assert summary.latency_p95_seconds == 0.0
    assert summary.latency_p99_seconds == 0.0
    assert summary.cache_hit_rate == 0.0
    assert summary.mean_precision_at_k is None
