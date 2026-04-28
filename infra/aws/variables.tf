variable "project_name" {
  description = "Project/application name used for resource naming."
  type        = string
  default     = "tax-rag"
}

variable "environment" {
  description = "Environment name."
  type        = string
  default     = "dev"
}

variable "aws_region" {
  description = "AWS region for deployment."
  type        = string
  default     = "eu-central-1"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated VPC."
  type        = string
  default     = "10.42.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "Public subnet CIDRs."
  type        = list(string)
  default     = ["10.42.1.0/24", "10.42.2.0/24"]
}

variable "private_subnet_cidrs" {
  description = "Private subnet CIDRs."
  type        = list(string)
  default     = ["10.42.11.0/24", "10.42.12.0/24"]
}

variable "artifacts_bucket_name" {
  description = "Optional explicit S3 bucket name. Leave empty to auto-generate via prefix usage policy downstream."
  type        = string
  default     = ""
}

variable "opensearch_instance_type" {
  description = "OpenSearch instance type for light environments."
  type        = string
  default     = "t3.small.search"
}

variable "opensearch_volume_size" {
  description = "EBS volume size in GiB for OpenSearch."
  type        = number
  default     = 20
}

variable "redis_node_type" {
  description = "ElastiCache Redis node type for light environments."
  type        = string
  default     = "cache.t4g.micro"
}

variable "enable_opensearch" {
  description = "Whether to provision OpenSearch in this light stack."
  type        = bool
  default     = true
}

variable "enable_redis" {
  description = "Whether to provision ElastiCache Redis in this light stack."
  type        = bool
  default     = true
}

variable "opensearch_master_user_name" {
  description = "Master username for OpenSearch advanced security."
  type        = string
  default     = "taxragadmin"
}

variable "opensearch_master_user_password" {
  description = "Sensitive OpenSearch master password. Provide through tfvars, environment variable, or secret injection; do not commit a real value."
  type        = string
  sensitive   = true
}
