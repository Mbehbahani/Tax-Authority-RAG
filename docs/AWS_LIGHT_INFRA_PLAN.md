# AWS Light Infrastructure Plan

This is a future plan only. No immediate deployment is required. Development should be local-first, with AWS used only for explicit managed API compatibility checks unless the user requests deployment. See [`docs/DEVELOPMENT_DEPLOYMENT_STRATEGY.md`](DEVELOPMENT_DEPLOYMENT_STRATEGY.md).

## Services

- S3 for raw corpus, normalized artifacts, chunk manifests, embeddings metadata, and eval datasets.
- OpenSearch managed service for hybrid retrieval.
- Bedrock for LLM and embedding APIs.
- Redis/ElastiCache optional for conservative semantic cache.
- ECS Fargate optional for a simple containerized API if deployment is needed.
- IAM roles with least privilege.
- Secrets Manager or SSM Parameter Store for configuration and secrets.
- CloudWatch for logs, metrics, alarms, and audit trails.
- GitHub Actions for CI/CD.

## Non-Goals

- No real AWS deployment now.
- No credentials.
- No Kubernetes unless later justified by explicit operational requirements.

