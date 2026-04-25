# Module 3: Agentic RAG & Self-Healing

## Objective

Design deterministic corrective RAG using LangGraph so failed retrieval leads to bounded correction or abstention, not hallucination.

## Design

- Use a state machine, not an open-ended autonomous agent.
- Carry authorization context through every state: user id, roles, clearance, need-to-know scope, classification filters, corpus version, and audit id.
- Handle complex tax questions with query decomposition when the query contains multiple legal issues, tax years, entities, or requested comparisons.
- Use HyDE only as a bounded fallback for semantic expansion, never as evidence.
- Retrieve and rerank authorized chunks only.
- Grade retrieved context before generation.
- Generate only when the grader returns `Relevant` and citation metadata is complete.
- Abstain if evidence is irrelevant, unauthorized, conflicting, outdated, or citation-incomplete after bounded retries.

State flow:

```text
START
  -> AUTH_CONTEXT
  -> CLASSIFY_QUERY
  -> DECOMPOSE_QUERY?           # for multi-part questions
  -> RETRIEVE                   # RBAC-filtered hybrid retrieval
  -> RERANK                     # authorized candidates only
  -> GRADE_CONTEXT              # Relevant / Ambiguous / Irrelevant
  -> GENERATE_WITH_CITATIONS    # only if Relevant
  -> VALIDATE_CITATIONS
  -> END

GRADE_CONTEXT -> REWRITE_QUERY -> RETRIEVE     # if Irrelevant and retry available
GRADE_CONTEXT -> HYDE_QUERY -> RETRIEVE        # optional bounded semantic expansion
GRADE_CONTEXT -> DECOMPOSE_QUERY -> RETRIEVE   # if Ambiguous
GRADE_CONTEXT -> ABSTAIN                       # if retry exhausted or unsafe
VALIDATE_CITATIONS -> ABSTAIN                  # if citation validation fails
```

Retrieval grader labels:

- `Relevant`: context directly answers the question, is authorized, current for the requested tax period, and has exact citations.
- `Ambiguous`: context is partially relevant but multi-part, conflicting, missing effective-date clarity, or needs decomposition.
- `Irrelevant`: context does not answer the question, contains no authorized evidence, or only unauthorized relevant documents exist.

## Configs

- Max retrieval attempts: `2`.
- Max query rewrites: `1`.
- Max HyDE attempts: `1`.
- Max decomposition subqueries: `4`.
- Retrieval grader output: strict JSON with `label`, `confidence`, `reasons`, `missing_evidence`, and `required_action`.
- Relevant threshold: grader confidence `>= 0.75` and all required citation fields present.
- Ambiguous threshold: confidence `0.45-0.75`, conflict detected, or multi-part query unresolved.
- Irrelevant threshold: confidence `< 0.45`, no authorized context, or no citation-complete support.
- Generation prompt boundary: answer only from provided authorized chunks; cite each claim; abstain if unsupported.
- State transition fixtures: [`tests/unit/langgraph_crag_state_cases.json`](../tests/unit/langgraph_crag_state_cases.json).
- Retrieval grader fixtures: [`tests/eval/retrieval_grader_cases.json`](../tests/eval/retrieval_grader_cases.json).

## Pseudo-code

```python
class RagState(TypedDict):
    user: UserContext
    query: str
    decomposed_queries: list[str]
    retrieved_chunks: list[Chunk]
    reranked_chunks: list[Chunk]
    grade: dict
    attempts: int
    answer: str | None
    citations: list[Citation]


def grade_context(state: RagState) -> str:
    grade = retrieval_grader(
        query=state["query"],
        chunks=state["reranked_chunks"],
        required_fields=["document_name", "article", "paragraph"],
    )
    state["grade"] = grade

    if grade["label"] == "Relevant" and citations_complete(state["reranked_chunks"]):
        return "GENERATE_WITH_CITATIONS"

    if grade["label"] == "Ambiguous" and state["attempts"] < 2:
        return "DECOMPOSE_QUERY"

    if grade["label"] == "Irrelevant" and state["attempts"] < 2:
        return "REWRITE_QUERY"

    return "ABSTAIN"


def generate_with_citations(state: RagState) -> RagState:
    assert all(is_authorized(c, state["user"]) for c in state["reranked_chunks"])
    answer = llm_generate(
        system="Answer only from authorized context. Cite every claim. Abstain if unsupported.",
        context=state["reranked_chunks"][:8],
        question=state["query"],
    )
    state["answer"] = answer.text
    state["citations"] = answer.citations
    return state


def validate_citations(state: RagState) -> str:
    authorized_ids = {c.chunk_id for c in state["reranked_chunks"]}
    if not state["citations"]:
        return "ABSTAIN"
    if any(c.chunk_id not in authorized_ids for c in state["citations"]):
        return "ABSTAIN"
    if any(not has_exact_document_article_paragraph(c) for c in state["citations"]):
        return "ABSTAIN"
    return "END"
```

## Tests

- Unit tests for all graph transitions in [`tests/unit/langgraph_crag_state_cases.json`](../tests/unit/langgraph_crag_state_cases.json).
- Grader tests for `Relevant`, `Ambiguous`, and `Irrelevant` in [`tests/eval/retrieval_grader_cases.json`](../tests/eval/retrieval_grader_cases.json).
- Query decomposition test for multi-part tax question with tax year and document type constraints.
- HyDE test ensures hypothetical text is used only for retrieval expansion, never as cited evidence.
- Irrelevant retrieval test triggers bounded rewrite and then abstention if still unsupported.
- Ambiguous version conflict triggers decomposition or clarification, not generation.
- Unauthorized-only relevant evidence triggers abstention with no leakage.
- Citation validation failure triggers abstention.
- Prompt injection test confirms user cannot force generation from missing or unauthorized context.

## Tradeoffs

- Deterministic LangGraph transitions improve auditability and reduce hallucination risk compared with free-form agents.
- Query decomposition improves complex-question accuracy but increases retrieval calls and latency.
- HyDE can improve semantic recall but is risky in legal domains; use only as bounded retrieval expansion, never as evidence.
- Low retry limits protect TTFT and prevent runaway cost.
- Abstention is preferable to unsupported fiscal advice.

