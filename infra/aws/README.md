# AWS Light Terraform Skeleton

This directory provides a **light, implementation-ready Terraform starting point**
for the Tax Authority RAG system.

It is intentionally **small and concrete**:

- Bedrock stays managed and is consumed by the app at runtime.
- S3 stores corpus artifacts and evaluation data.
- OpenSearch provides hybrid retrieval.
- Redis/ElastiCache provides semantic cache.
- ECS is represented as the target runtime direction without forcing a full
  production deployment in this skeleton.

## Files

- `versions.tf` — provider and Terraform version constraints
- `variables.tf` — deployment inputs
- `main.tf` — core AWS resources
- `outputs.tf` — useful outputs after apply
- `terraform.tfvars.example` — example values

## Intended Use

1. Review and adjust naming, CIDR, and sizing.
2. Add ECS task definition / service wiring if the team wants immediate runtime deployment.
3. Keep secrets out of Terraform code; use IAM roles, SSM, or Secrets Manager.

## Secret Handling

- `opensearch_master_user_password` is intentionally **not** given a default.
- Provide it via a local `terraform.tfvars`, `TF_VAR_opensearch_master_user_password`,
  CI secret injection, or a future Secrets Manager integration.
- Do **not** commit a real password into this repository.

## Notes

- This repository currently does **not** include the Terraform binary locally.
- The skeleton is designed to be low-risk and easy for a DevOps team to extend.
- Default region is `eu-central-1` to align with Bedrock usage in this project.

## Real Deployment Test Result

A minimal real AWS smoke test was executed successfully in `eu-central-1` using
the current account access.

Created and verified resources:

- **S3 bucket**: `tax-rag-dev-780822965578-20260428`
- **CloudWatch log group**: `/aws/tax-rag-dev/api`
- **ECS cluster**: `tax-rag-dev-cluster`

Observed result:

- AWS CLI identity and permissions were working correctly.
- The account could create baseline infrastructure resources needed for an AWS deployment path.
- This confirms that the project is no longer only a local Docker design; it has been partially validated against real AWS resources.

Current limitation:

- This was a **minimal infrastructure smoke test**, not a full application deployment.
- OpenSearch, Redis, ECS task definition/service wiring, IAM task roles, and runtime container deployment are still the next implementation steps.
- Local Terraform validation could not yet be executed because the Terraform binary is not installed on this machine.
