output "vpc_id" {
  value       = aws_vpc.main.id
  description = "Created VPC ID."
}

output "public_subnet_ids" {
  value       = aws_subnet.public[*].id
  description = "Public subnet IDs."
}

output "private_subnet_ids" {
  value       = aws_subnet.private[*].id
  description = "Private subnet IDs."
}

output "artifacts_bucket_name" {
  value       = aws_s3_bucket.artifacts.bucket
  description = "Artifacts bucket name."
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.main.name
  description = "ECS cluster name for future API deployment."
}

output "opensearch_endpoint" {
  value       = var.enable_opensearch ? aws_opensearch_domain.main[0].endpoint : null
  description = "OpenSearch endpoint if enabled."
}

output "redis_endpoint" {
  value       = var.enable_redis ? aws_elasticache_cluster.redis[0].cache_nodes[0].address : null
  description = "Redis endpoint if enabled."
}
