output "vpc_id" {
  description = "The ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "List of IDs of public subnets"
  value       = aws_subnet.public[*].id
}

output "private_app_subnet_ids" {
  description = "List of IDs of private application subnets"
  value       = aws_subnet.private_app[*].id
}

output "private_db_subnet_ids" {
  description = "List of IDs of private database subnets"
  value       = aws_subnet.private_db[*].id
}

output "db_subnet_group_name" {
  description = "The name of the RDS DB subnet group"
  value       = aws_db_subnet_group.main.name
}

output "security_group_alb_id" {
  description = "The ID of the ALB security group"
  value       = aws_security_group.alb.id
}

output "security_group_app_id" {
  description = "The ID of the application compute security group"
  value       = aws_security_group.app.id
}

output "security_group_db_id" {
  description = "The ID of the database security group"
  value       = aws_security_group.db.id
}

output "rds_endpoint" {
  description = "The connection endpoint for the RDS PostgreSQL instance"
  value       = aws_db_instance.postgres.endpoint
}

output "rds_address" {
  description = "The hostname address of the RDS database"
  value       = aws_db_instance.postgres.address
}

output "rds_secret_arn" {
  description = "The ARN of the AWS Secrets Manager secret storing database credentials"
  value       = aws_secretsmanager_secret.db_credentials.arn
}

output "k3s_server_public_ip" {
  description = "Public IPv4 address of the k3s Kubernetes server"
  value       = aws_instance.k3s_server.public_ip
}

output "k3s_server_instance_id" {
  description = "EC2 instance ID of the k3s Kubernetes server"
  value       = aws_instance.k3s_server.id
}


