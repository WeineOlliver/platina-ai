variable "aws_region" {
  description = "Target AWS region for deploying Platina AI cloud infrastructure"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated Platina AI VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "db_name" {
  description = "Initial database name for PostgreSQL RDS"
  type        = string
  default     = "platina_rag"
}

variable "db_username" {
  description = "Master username for PostgreSQL RDS"
  type        = string
  default     = "platina_admin"
}
