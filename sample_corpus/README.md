# Sample Corpus for Local Tests

This synthetic corpus exists only for local PoC and automated test design. It is not real fiscal advice and must not be treated as legal source material.

## Corpus Types

- [`legislation/income_tax_act_2024.md`](legislation/income_tax_act_2024.md): current hierarchical legislation.
- [`legislation/income_tax_act_2022_historical.md`](legislation/income_tax_act_2022_historical.md): historical legal text for version/effective-date tests.
- [`case_law/supreme_court_home_office_2023.md`](case_law/supreme_court_home_office_2023.md): dense case-law style ruling with ECLI identifier.
- [`policies/helpdesk_home_office_guideline.md`](policies/helpdesk_home_office_guideline.md): internal policy guideline visible to helpdesk.
- [`policies/fiod_fraud_investigation_memo.md`](policies/fiod_fraud_investigation_memo.md): restricted FIOD-style memo for RBAC denial tests.
- [`elearning/home_office_deduction_training.md`](elearning/home_office_deduction_training.md): e-learning/wiki-style training content.

## Test Purpose

Use these documents to validate:

- legal hierarchy extraction;
- historical/current version handling;
- exact citation formatting;
- exact identifier retrieval such as ECLI;
- semantic retrieval;
- RBAC filtering before retrieval;
- zero-hallucination abstention;
- prompt construction with authorized chunks only.

