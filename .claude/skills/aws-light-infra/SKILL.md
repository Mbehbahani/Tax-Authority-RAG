---
name: aws-light-infra
description: Guidance for optional light AWS planning with S3, OpenSearch, Bedrock, Redis/ElastiCache, IAM, secrets, and observability without overbuilding deployment.
---

# Skill: AWS Light Infrastructure

Use this skill only when light AWS future planning is needed.

## Guidance

- AWS is optional and not the main assessment deliverable.
- S3 stores raw corpus, normalized artifacts, chunk manifests, and evaluation datasets.
- OpenSearch managed service provides hybrid retrieval.
- Bedrock provides enterprise-approved LLM and embedding APIs.
- Redis/ElastiCache is optional for conservative semantic cache.
- ECS Fargate or a simple containerized service is enough if deployment is requested.
- Use IAM roles and least privilege.
- Store secrets in Secrets Manager or SSM Parameter Store.
- Use CloudWatch for logs, metrics, and alarms.
- Do not recommend Kubernetes unless clearly justified.

