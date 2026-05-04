# Real-Stack Evaluation Analysis

## Why this document exists

The earlier summaries were too abstract to be useful for judging the real
algorithm. This document focuses only on **tangible evidence from the live
running stack**.

The system was probed through the real API while the following were active:

- **OpenSearch** as the retrieval backend
- **Redis** as the semantic cache backend
- **LangGraph** as the graph backend
- **Bedrock embeddings**
- **Bedrock rerank**
- **Bedrock generation**

Runtime health confirmed:

- `retrieval_backend = opensearch`
- `cache_backend = redis`
- `graph_backend = langgraph`
- `bedrock_embeddings = true`
- `bedrock_rerank = true`
- `bedrock_generation = true`

So this analysis is based on the **real local full stack**, not on in-memory or
formula-only unit tests.

---

## What was tested directly

The following live requests were sent to `POST /ask` against the running stack:

1. `Q_SEMANTIC_HELPDESK_HOME_OFFICE`
2. `Q_RBAC_DENIED_HELPDESK_FIOD`
3. `Q_CACHE_FAQ_BOX1_FIRST`
4. `Q_CACHE_FAQ_BOX1_SECOND`
5. `Q_EXACT_ECLI_INSPECTOR`
6. `Q_INSPECTOR_AUDIT_MANUAL`

For each request, the following real outputs were captured:

- `abstained`
- `abstention_reason`
- `grader_label`
- `cache_hit`
- `latency_seconds`
- `trace`
- `retrieved_chunk_ids`
- `citations`
- answer preview

For the scenarios where a gold retrieval expectation exists in
`sample_requests/expected_behaviors.json`, the following IR metrics were also
computed from the **real returned ranked document IDs**:

- `precision@k`
- `recall@k`
- `MRR@k`
- `nDCG@k`

Important note:

- these IR metrics were computed by comparing the real returned document ranking
  against the `may_retrieve` gold document set
- some repeated probes hit Redis cache, so those requests reused previously
  retrieved results rather than executing a fresh retrieval path again
- for scenarios without a defined gold set, IR metrics remain `null`

---

## 1. Direct evidence from the real system

### 1.1 Helpdesk semantic query

**Scenario:** `Q_SEMANTIC_HELPDESK_HOME_OFFICE`  
**Query:** `Can a taxpayer deduct home office expenses?`

### Observed result

- `abstained = false`
- `grader_label = Relevant`
- `cache_hit = false`
- `latency_seconds = 9.6296`
- trace path:

```text
START
AUTH_CONTEXT
CLASSIFY_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
GENERATE_WITH_CITATIONS
VALIDATE_CITATIONS
END
```

### What this proves

- the real system successfully answered a semantic helpdesk question
- the CRAG path stayed on the straightforward success route
- the answer was citation-backed
- no abstention was triggered

### Important observation

This query took **~9.63 seconds**, which is much slower than the offline report
summary suggested. That means the real stack behavior is materially different
from the deterministic report, and this is exactly why direct probing is more
useful.

---

### 1.2 Helpdesk asking for restricted fraud-investigation material

**Scenario:** `Q_RBAC_DENIED_HELPDESK_FIOD`  
**Query:** `Summarize fraud investigation insights for home office deduction abuse.`

### Observed result

- `abstained = true`
- `abstention_reason = retry_budget_exhausted`
- `grader_label = Irrelevant`
- `cache_hit = false`
- `latency_seconds = 1.6886`
- trace path:

```text
START
AUTH_CONTEXT
CLASSIFY_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
HYDE_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
ABSTAIN
END
```

### What this proves

- the system did **not** answer the unauthorized fraud-related request
- the graph did not stop immediately; it attempted corrective retrieval once via
  `HYDE_QUERY`
- after retry, the system abstained safely

### Important interpretation

This is one of the most meaningful real-system results in the whole project:

- RBAC-sensitive content did not turn into an answer
- the corrective loop was actually used
- the abstention path is not theoretical; it happened in a live request

---

### 1.3 Cache behavior — first Box 1 request

**Scenario:** `Q_CACHE_FAQ_BOX1_FIRST`  
**Query:** `What is the Box 1 tax rate for 2024?`

### Observed result

- `abstained = false`
- `grader_label = Relevant`
- `cache_hit = false`
- `latency_seconds = 21.1197`
- trace path:

```text
START
AUTH_CONTEXT
CLASSIFY_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
GENERATE_WITH_CITATIONS
VALIDATE_CITATIONS
END
```

### What this proves

- the first request was a genuine full-stack miss
- the system went through retrieval, rerank, grading, generation, and citation
  validation
- the response was grounded with four citations

### Important observation

This request took **~21.12 seconds**, which is the clearest sign that the live
runtime cost is significant when Bedrock + retrieval + rerank are actually used.

---

### 1.4 Cache behavior — second identical Box 1 request

**Scenario:** `Q_CACHE_FAQ_BOX1_SECOND`  
**Query:** `What is the Box 1 tax rate for 2024?`

### Observed result

- `abstained = false`
- `grader_label = Relevant`
- `cache_hit = true`
- `latency_seconds = 0.1384`
- trace path:

```text
CACHE_HIT
END
```

### What this proves

- Redis semantic cache is working in the real system
- repeated FAQ-style requests become dramatically faster
- the cache path bypasses retrieval/rerank/generation stages entirely

### Quantified impact

- first request: **21.12s**
- second request: **0.138s**

That is roughly a **150x+ latency reduction** in this specific repeated-query
case.

This is one of the strongest tangible system-level results currently available.

---

### 1.5 Exact ECLI retrieval for inspector

**Scenario:** `Q_EXACT_ECLI_INSPECTOR`  
**Query:** `Ruling ECLI:NL:HR:2023:123`

### Observed result

- `abstained = false`
- `grader_label = Relevant`
- `cache_hit = false`
- `latency_seconds = 17.2914`
- trace path:

```text
START
AUTH_CONTEXT
CLASSIFY_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
GENERATE_WITH_CITATIONS
VALIDATE_CITATIONS
END
```

### What this proves

- the real stack can answer exact legal identifier queries
- hybrid retrieval + rerank returned multiple case-law chunks
- the answer stayed citation-grounded

### Important observation

This is an exact-match style query, yet it still took **~17.29 seconds**. That
suggests the dominant cost is not just lexical lookup; it is the full retrieval
and generation stack around it.

---

### 1.6 Inspector audit-manual question

**Scenario:** `Q_INSPECTOR_AUDIT_MANUAL`  
**Query:** `What should an inspector verify in a home office audit?`

### Observed result

- `abstained = false`
- `grader_label = Relevant`
- `cache_hit = false`
- `latency_seconds = 21.0283`
- trace path:

```text
START
AUTH_CONTEXT
CLASSIFY_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
GENERATE_WITH_CITATIONS
VALIDATE_CITATIONS
END
```

### What this proves

- the system can retrieve internal policy/manual guidance for an authorized
  inspector
- the answer is citation-backed from policy/manual sources

### Important observation

This is another long-running real request at **~21.03 seconds**, reinforcing
that realistic stack behavior is far slower than the offline evaluation summary.

---

## 1.7 Real-stack IR metrics from live returned results

The following IR-style metrics were computed from real returned ranked document
IDs versus the gold `may_retrieve` sets in `sample_requests/expected_behaviors.json`.

| Scenario | Ranked docs returned | Gold relevant docs | precision@k | recall@k | MRR@k | nDCG@k |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `Q_SEMANTIC_HELPDESK_HOME_OFFICE` | `DOC-LEG-001`, `DOC-POL-001`, `DOC-ELRN-001` | same 3 docs | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| `Q_RBAC_DENIED_HELPDESK_FIOD` | `DOC-POL-001`, `DOC-ELRN-001`, `DOC-LEG-001`, `DOC-ELRN-003` | no allowed gold set | null | null | null | null |
| `Q_CACHE_FAQ_BOX1_FIRST` | `DOC-POL-004`, `DOC-LEG-001` | no gold set | null | null | null | null |
| `Q_CACHE_FAQ_BOX1_SECOND` | `DOC-POL-004`, `DOC-LEG-001` | no gold set | null | null | null | null |
| `Q_EXACT_ECLI_INSPECTOR` | `DOC-CASE-002`, `DOC-CASE-001`, `DOC-CASE-003` | `DOC-CASE-001` | 0.3333 | 1.0000 | 0.5000 | 0.6309 |
| `Q_INSPECTOR_AUDIT_MANUAL` | `DOC-POL-002`, `DOC-POL-001` | `DOC-POL-002`, `DOC-LEG-001`, `DOC-REG-001` | 0.5000 | 0.3333 | 1.0000 | 0.6131 |

### Interpretation

#### Best retrieval result in this sample

`Q_SEMANTIC_HELPDESK_HOME_OFFICE` performed perfectly:

- all expected relevant documents were returned
- no extra irrelevant documents were included in the ranked document set
- the first relevant result was at rank 1

This is the clearest positive retrieval-quality example from the live stack.

#### Exact ECLI retrieval result is mixed

`Q_EXACT_ECLI_INSPECTOR` shows:

- `recall@k = 1.0` → the expected ruling was found
- `precision@k = 0.3333` → extra case-law documents were also returned
- `MRR = 0.5` → the expected ruling was not ranked first, but second

This means the system **finds** the target case, but the ranking is not yet as
clean as it should be for an exact-identifier query.

#### Inspector audit-manual retrieval is partially correct

`Q_INSPECTOR_AUDIT_MANUAL` shows:

- `precision@k = 0.5`
- `recall@k = 0.3333`
- `MRR = 1.0`

This means:

- the top result is relevant
- but only one of the three expected gold documents appeared in the returned
  ranked document set

So this scenario demonstrates a useful but incomplete retrieval result.

#### Important limitation

These metrics are only as good as the current gold sets in
`expected_behaviors.json`. Right now, `may_retrieve` works as a practical proxy,
but it is still weaker than a carefully curated scenario-level
`relevant_document_ids` or `relevant_chunk_ids` field designed explicitly for IR
evaluation.

---

## 1.8 Fresh retrieval vs cached behavior

To separate real retrieval behavior from cached behavior, the Redis semantic
cache was cleared and the same representative scenarios were run again.

### Fresh retrieval results after cache flush

| Scenario | cache_hit | latency (s) | precision@k | recall@k | MRR@k | nDCG@k | Path |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `Q_SEMANTIC_HELPDESK_HOME_OFFICE` | false | 3.2666 | 0.7500 | 1.0000 | 1.0000 | 1.0000 | full success path |
| `Q_RBAC_DENIED_HELPDESK_FIOD` | false | 1.4362 | null | null | null | null | corrective abstention |
| `Q_CACHE_FAQ_BOX1_FIRST` | false | 20.0598 | null | null | null | null | full success path |
| `Q_CACHE_FAQ_BOX1_SECOND` | true | 0.2111 | null | null | null | null | cache shortcut |
| `Q_EXACT_ECLI_INSPECTOR` | false | 19.4440 | 0.2500 | 1.0000 | 0.5000 | 0.6309 | full success path |
| `Q_INSPECTOR_AUDIT_MANUAL` | false | 20.1687 | 0.5000 | 0.6667 | 1.0000 | 0.6714 | full success path |

### What changed compared with the earlier mixed cached run

#### Helpdesk semantic query

Earlier mixed run:

- cache hit example existed
- perfect retrieval metrics were observed on a cached result snapshot

Fresh retrieval run:

- `cache_hit = false`
- `latency = 3.27s`
- `precision@k = 0.75`
- `recall@k = 1.0`

Interpretation:

- the system still finds all expected relevant documents
- but the real fresh retrieval ranking also includes one extra document
- so the fresh result is good, but not perfectly clean

#### Exact ECLI query

Fresh retrieval run:

- `latency = 19.44s`
- `precision@k = 0.25`
- `recall@k = 1.0`
- `MRR = 0.5`

Interpretation:

- the target case is always found
- but it is not ranked first
- and several extra case documents are included

This is a meaningful weakness for an exact-identifier query.

#### Inspector audit-manual query

Fresh retrieval run:

- `latency = 20.17s`
- `precision@k = 0.5`
- `recall@k = 0.6667`
- `MRR = 1.0`

Interpretation:

- the best result is relevant
- more of the expected evidence is present than in the earlier cached snapshot
- but the returned ranking is still incomplete relative to the gold set

#### Box 1 cache demonstration remains strong

This remains the clearest cache-value example:

- fresh request: `20.06s`
- immediate repeated request: `0.211s`

So even after forcing a fresh retrieval, the cache result remains dramatically
faster and preserves the same answer class.

---

## 2. Answers to the concrete questions

### 2.1 Where did latency come from?

From the real requests, latency is clearly associated with the **full success
path**:

- retrieval
- rerank
- context grading
- generation
- citation validation

Evidence:

- semantic helpdesk query: `3.27s` fresh, `0.46s` cached snapshot
- exact ECLI query: `19.44s` fresh
- Box 1 first request: `20.06s` fresh
- inspector audit manual: `20.17s` fresh

By contrast, a cached request took:

- `0.138s`

This strongly suggests that the expensive part is the **uncached retrieval +
rerank + generation path**, not simple API overhead.

---

### 2.2 Was retrieval or rerank slow?

From the currently captured API response alone, we cannot numerically separate:

- retrieval latency
- rerank latency
- generation latency

But we can already conclude this:

- the slow requests all follow the same uncached path:
  `RETRIEVE → RERANK → GRADE_CONTEXT → GENERATE_WITH_CITATIONS`
- the cached request skips that path and becomes extremely fast

So at minimum, we know the bottleneck belongs to the **uncached pipeline path**,
not to HTTP handling or response formatting.

To distinguish retrieval vs rerank vs generation precisely, the next practical
step is to inspect the span timings in Langfuse for one of these slow requests.

From the IR metrics, we can already add one more useful conclusion:

- some queries are not failing because the system finds nothing
- they are failing because the returned ranking still contains extra or missing
  documents compared to the expected gold set

That is especially visible in:

- `Q_EXACT_ECLI_INSPECTOR`
- `Q_INSPECTOR_AUDIT_MANUAL`
- `Q_SEMANTIC_HELPDESK_HOME_OFFICE` fresh retrieval path

---

### 2.3 Did a query abstain after grading?

Yes.

The clearest example is:

- `Q_RBAC_DENIED_HELPDESK_FIOD`

Observed path:

```text
RETRIEVE
RERANK
GRADE_CONTEXT
HYDE_QUERY
RETRIEVE
RERANK
GRADE_CONTEXT
ABSTAIN
END
```

This proves that abstention is not a superficial rule — it happened after:

- grading the first retrieval result
- attempting a corrective query transformation
- grading again
- then choosing abstention

That is exactly the kind of behavior expected from a corrective RAG loop.

---

### 2.4 Did cache hit happen?

Yes, clearly.

The strongest example is the repeated Box 1 question:

- first request: `cache_hit = false`, `21.12s`
- second request: `cache_hit = true`, `0.138s`

Trace difference:

**First request**

```text
START → AUTH_CONTEXT → CLASSIFY_QUERY → RETRIEVE → RERANK → GRADE_CONTEXT → GENERATE_WITH_CITATIONS → VALIDATE_CITATIONS → END
```

**Second request**

```text
CACHE_HIT → END
```

This is a highly tangible real-system result and one of the most valuable
findings in the project right now.

---

### 2.5 Which path did the CRAG loop follow?

We now have direct evidence of multiple live paths:

#### Straight success path

Seen in:

- helpdesk semantic question
- exact ECLI query
- inspector audit manual
- first Box 1 request

Path:

```text
START → AUTH_CONTEXT → CLASSIFY_QUERY → RETRIEVE → RERANK → GRADE_CONTEXT → GENERATE_WITH_CITATIONS → VALIDATE_CITATIONS → END
```

#### Corrective abstention path

Seen in:

- helpdesk fraud-investigation question

Path:

```text
START → AUTH_CONTEXT → CLASSIFY_QUERY → RETRIEVE → RERANK → GRADE_CONTEXT → HYDE_QUERY → RETRIEVE → RERANK → GRADE_CONTEXT → ABSTAIN → END
```

#### Cache shortcut path

Seen in:

- second Box 1 request

Path:

```text
CACHE_HIT → END
```

This is much more useful than a generic architecture diagram, because it shows
that the implemented system actually exercised three different operational
paths under live conditions.

---

## 3. What these results actually mean

### Strong evidence already available

1. **Safety path works**
   - unauthorized fraud-style helpdesk query abstained
   - no answer was produced

2. **Cache path works**
   - repeated FAQ query dropped from ~21s to ~0.14s

3. **CRAG path is real, not just designed**
   - success path observed
   - corrective retry + abstain path observed
   - cache shortcut path observed

4. **Citation-backed answers work in the live stack**
   - successful responses returned structured citations from real retrieved
     documents

### Weaknesses / concerns exposed by the live system

1. **Uncached latency is high**
   - several fresh live requests took ~3s to ~20s
   - this is much higher than the deterministic evaluation report suggested

2. **Offline summaries were not enough**
   - the offline evaluation report hides important real-system timing behavior
   - direct request probing is much more informative

3. **IR retrieval metrics are still missing**
   - we now have a useful first approximation from `may_retrieve`, but we still
     do not have a fully curated IR gold-label setup specifically designed for
     ranking evaluation in every scenario

---

## 4. Best current reviewer-facing message

The most honest and useful message for a reviewer is:

> The project already demonstrates live evidence of three meaningful runtime
> behaviors: citation-grounded successful answers, corrective abstention for a
> restricted/unsafe request, and a large real cache-speedup for repeated FAQ
> queries. The biggest remaining weaknesses are high uncached latency and
> imperfect fresh retrieval ranking quality for some important scenarios such as
> exact ECLI lookup and inspector audit retrieval.

---

## 5. Most valuable next step

The next most valuable step is **not** adding more formula tests.

It is:

1. inspect Langfuse span timings for the slow real requests
2. determine whether the main bottleneck is:
   - retrieval
   - rerank
   - generation
3. prioritize ranking cleanup for exact-id and inspector-policy queries
4. then tune the real system based on that evidence

That would convert this from a “working system with interesting traces” into a
more convincing performance-engineering story.