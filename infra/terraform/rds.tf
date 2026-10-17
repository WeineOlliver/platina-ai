# Generate cryptographically secure random master password for RDS
resource "random_password" "db_password" {
  length           = 24
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

# AWS Secrets Manager Secret container
resource "aws_secretsmanager_secret" "db_credentials" {
  name        = "platina-ai/${var.environment}/rds-credentials"
  description = "Managed master credentials and connection string for Platina AI PostgreSQL database"

  recovery_window_in_days = 0 # Instant removal on terraform destroy for portfolio tear-down
}

# Custom Parameter Group enabling pgvector extension
resource "aws_db_parameter_group" "pg16" {
  name        = "platina-pg16-params-${var.environment}"
  family      = "postgres16"
  description = "Custom RDS Parameter Group for PostgreSQL 16 with pgvector support"

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  tags = {
    Name = "platina-pg16-parameters"
  }
}

# Production-grade Managed PostgreSQL RDS instance
resource "aws_db_instance" "postgres" {
  identifier        = "platina-db-${var.environment}"
  engine            = "postgres"
  engine_version    = "16.4"
  instance_class    = "db.t4g.micro" # Cost-effective AWS Graviton2 instance
  allocated_storage = 20
  max_allocated_storage = 50
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db_password.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  parameter_group_name   = aws_db_parameter_group.pg16.name

  publicly_accessible = false
  skip_final_snapshot = true
  deletion_protection = false

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Sun:04:30-Sun:05:30"

  tags = {
    Name = "platina-rds-postgres"
  }
}

# Store secret payload in Secrets Manager including the live RDS endpoint
resource "aws_secretsmanager_secret_version" "db_credentials" {
  secret_id = aws_secretsmanager_secret.db_credentials.id
  secret_string = jsonencode({
    engine   = "postgres"
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    database = var.db_name
    username = var.db_username
    password = random_password.db_password.result
    url      = "postgresql://${var.db_username}:${random_password.db_password.result}@${aws_db_instance.postgres.endpoint}/${var.db_name}"
  })
}
