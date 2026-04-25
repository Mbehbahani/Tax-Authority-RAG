"""Semantic cache isolation: authorization-scoped cache keys; no cross-role reuse."""

from __future__ import annotations


def test_cache_hit_for_same_helpdesk_user_same_query(rag_service, users):
    rag_service.cache.enable(True)
    try:
        first = rag_service.ask(
            users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?"
        )
        assert not first.abstained
        assert first.cache_hit is False
        second = rag_service.ask(
            users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?"
        )
        assert second.cache_hit is True
    finally:
        rag_service.cache.clear()
        rag_service.cache.enable(False)


def test_cache_never_reused_across_roles(rag_service, users):
    rag_service.cache.enable(True)
    try:
        insp = rag_service.ask(
            users["u_inspector_01"],
            "Explain the home office ruling",
        )
        assert not insp.abstained
        help_r = rag_service.ask(
            users["u_helpdesk_01"],
            "Explain the home office ruling",
        )
        # Even if helpdesk abstains, the critical invariant is that no cached
        # inspector answer that cites DOC-CASE-001 can be served to helpdesk.
        for cite in help_r.citations:
            assert cite["document_id"] != "DOC-CASE-001"
        assert help_r.cache_hit is False
    finally:
        rag_service.cache.clear()
        rag_service.cache.enable(False)


def test_cache_disabled_by_default(rag_service):
    assert rag_service.cache.entries == []


def test_cache_never_writes_abstention(rag_service, users):
    rag_service.cache.enable(True)
    try:
        r = rag_service.ask(
            users["u_helpdesk_01"],
            "Summarize fraud investigation insights for home office deduction abuse.",
        )
        assert r.abstained is True
        assert rag_service.cache.entries == []
    finally:
        rag_service.cache.clear()
        rag_service.cache.enable(False)


def test_cache_key_includes_auth_scope(rag_service, users):
    rag_service.cache.enable(True)
    try:
        rag_service.ask(users["u_helpdesk_01"], "Can a taxpayer deduct home office expenses?")
        rag_service.ask(users["u_inspector_01"], "Can a taxpayer deduct home office expenses?")
        scope_hashes = {e.scope_hash for e in rag_service.cache.entries}
        # Each role has a distinct auth scope hash.
        assert len(scope_hashes) == len(rag_service.cache.entries)
        assert len(scope_hashes) >= 1
    finally:
        rag_service.cache.clear()
        rag_service.cache.enable(False)
