"""Integration-level retrieval and citation tests.

These run against the in-memory OpenSearch-compatible backend. They assert the
same queries would behave correctly against a real OpenSearch cluster because
both backends share one auth filter and the index-mapping/query contract.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.rag.retrieval import (
    DEFAULT_FINAL_TOP_N,
    build_index_mapping,
    build_opensearch_queries,
    hybrid_retrieve,
)
from app.rag.security import build_auth_filter

ROOT = Path(__file__).resolve().parent.parent.parent
QUERY_FIXTURES = json.loads(
    (ROOT / "tests" / "integration" / "retrieval_query_examples.json").read_text()
)
EXPECTED_INDEX = json.loads(
    (ROOT / "tests" / "integration" / "opensearch_index_config_expected.json").read_text()
)


def test_exact_ecli_retrieves_case_law_for_inspector(rag_service, users):
    r = rag_service.ask(users["u_inspector_01"], "Ruling ECLI:NL:HR:2023:123")
    assert not r.abstained
    assert any(c["document_id"] == "DOC-CASE-001" for c in r.citations)
    # Must not leak FIOD even though user has clearance 3.
    for c in r.citations:
        assert c["document_id"] != "DOC-FIOD-001"


def test_helpdesk_semantic_home_office_uses_helpdesk_safe_docs(rag_service, users):
    r = rag_service.ask(users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?")
    assert not r.abstained
    cited = {c["document_id"] for c in r.citations}
    assert cited.issubset({"DOC-LEG-001", "DOC-POL-001", "DOC-ELRN-001"})
    assert "DOC-CASE-001" not in cited  # case law is not helpdesk-authorized
    assert "DOC-FIOD-001" not in cited


def test_legal_counsel_can_use_legislation_and_case_law(rag_service, users):
    r = rag_service.ask(
        users["u_legal_01"],
        "What is the legal interpretation of home office deduction after ECLI:NL:HR:2023:123?",
    )
    assert not r.abstained
    cited = {c["document_id"] for c in r.citations}
    assert "DOC-CASE-001" in cited or "DOC-LEG-001" in cited


def test_final_context_is_bounded(rag_service, users):
    r = rag_service.ask(users["u_inspector_01"], "home office documentation duties")
    assert len(r.citations) <= DEFAULT_FINAL_TOP_N
    assert len(r.retrieved_chunk_ids) <= DEFAULT_FINAL_TOP_N


def test_retrieval_respects_top_k_and_fused_candidates(backend, embedder, users):
    query = "home office deduction"
    final_context, debug = hybrid_retrieve(
        query=query, user=users["u_inspector_01"], backend=backend, embedder=embedder
    )
    assert len(debug["lexical_chunk_ids"]) <= 50
    assert len(debug["vector_chunk_ids"]) <= 50
    assert len(debug["fused_chunk_ids"]) <= 80
    assert len(debug["reranked_chunk_ids"]) <= 60
    assert len(debug["final_chunk_ids"]) <= 8


# ------------------------ OpenSearch contract tests -------------------------


def test_index_mapping_includes_all_required_fields():
    mapping = build_index_mapping()
    props = mapping["mappings"]["properties"]
    for field in EXPECTED_INDEX["required_fields"]:
        assert field in props, f"missing field {field} in mapping"


def test_index_mapping_has_hnsw_and_knn_settings():
    mapping = build_index_mapping()
    emb = mapping["mappings"]["properties"]["embedding"]
    assert emb["type"] == "knn_vector"
    assert emb["method"]["name"] == "hnsw"
    assert emb["method"]["parameters"]["m"] == 32
    assert emb["method"]["parameters"]["ef_construction"] == 256
    settings = mapping["settings"]
    assert settings["index.knn"] is True
    assert settings["index.knn.algo_param.ef_search"] == 128


def test_opensearch_query_contains_rbac_filters_and_boosts(users, embedder):
    auth = build_auth_filter(users["u_helpdesk_01"])
    qs = build_opensearch_queries(
        query_text="home office deduction",
        query_embedding=embedder.embed("home office deduction"),
        auth_filter=auth.to_opensearch_filter(),
    )
    lex = qs["lexical"]["query"]["bool"]
    assert {"term": {"allowed_roles": "helpdesk"}} in lex["filter"]
    assert any("range" in f for f in lex["filter"])
    must_not_terms = {list(f["term"].values())[0] for f in lex["must_not"]}
    assert {"FIOD", "fraud_investigation"}.issubset(must_not_terms)

    multi_match = lex["must"][0]["multi_match"]
    assert "ecli^12" in multi_match["fields"]
    assert "document_id^8" in multi_match["fields"]
    assert "article^5" in multi_match["fields"]
    assert "text^2" in multi_match["fields"]

    vec = qs["vector"]["query"]["bool"]
    knn = vec["must"][0]["knn"]["embedding"]
    assert knn["k"] == 50
    assert knn["method_parameters"]["ef_search"] == 128


def test_helpdesk_rbac_query_has_fiod_denial_filters(users, embedder):
    auth = build_auth_filter(users["u_helpdesk_01"])
    body = auth.to_opensearch_filter()
    must_not_terms = {list(f["term"].values())[0] for f in body["bool"]["must_not"]}
    assert {"FIOD", "fraud_investigation"}.issubset(must_not_terms)


@pytest.mark.parametrize("fixture_id", [q["id"] for q in QUERY_FIXTURES["queries"]])
def test_retrieval_fixtures_produce_authorized_results(fixture_id, rag_service, users):
    fixture = next(q for q in QUERY_FIXTURES["queries"] if q["id"] == fixture_id)
    user = users[fixture["user_id"]]
    r = rag_service.ask(user, fixture["query_text"])
    forbidden = set(fixture.get("expected_must_not_retrieve", []))
    for chunk_id in r.retrieved_chunk_ids:
        for f in forbidden:
            assert f not in chunk_id, f"{fixture_id} leaked {f}"
    for c in r.citations:
        assert c["document_id"] not in forbidden
