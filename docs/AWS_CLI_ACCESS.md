# AWS CLI Access for Local Verification

Use this file only when the user explicitly asks to verify AWS CLI, Bedrock model catalog, or Bedrock runtime access from the local development machine.

## Access Method

Use the AWS CLI configuration already available on the machine. Do not request, create, write, or commit static AWS credentials.

Preferred access mechanisms:

- existing AWS CLI default profile;
- configured named AWS profile;
- AWS SSO;
- IAM role-based access in deployed environments.

## Region

Use the EU region:

```text
eu-central-1
```

## Verification Commands

Verify CLI identity:

```text
aws sts get-caller-identity --output json
```

List Bedrock models in the target region:

```text
aws bedrock list-foundation-models --region eu-central-1 --output json
```

Filter for project-relevant Bedrock models:

```text
aws bedrock list-foundation-models --region eu-central-1 --query "modelSummaries[?contains(modelId, 'cohere.embed-v4') || contains(modelId, 'cohere.rerank-v3-5') || contains(modelId, 'anthropic.claude-3-haiku') || contains(modelId, 'anthropic.claude-3-7-sonnet') || contains(modelId, 'amazon.titan-embed-text-v2')].[modelId,modelName,providerName]" --output text
```

## Expected Project Model IDs

These model IDs were visible in the target region's Bedrock catalog during preparation:

```text
cohere.embed-v4:0
amazon.titan-embed-text-v2:0
anthropic.claude-3-haiku-20240307-v1:0
anthropic.claude-3-7-sonnet-20250219-v1:0
cohere.rerank-v3-5:0
```

Catalog visibility confirms model availability in the region. Runtime invocation access should still be tested before implementation depends on a model.

## Security Rules

- Never commit `.env`.
- Never commit AWS access keys, secret keys, or session tokens.
- Never write static AWS credentials into repository files.
- Use AWS profiles, SSO, IAM roles, Secrets Manager, or SSM Parameter Store.

