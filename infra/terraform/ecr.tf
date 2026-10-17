# AWS ECR Repositories for Platina AI Microservices
# Features: Tag immutability (reproducibility), Scan-on-push (CVE detection), and Lifecycle pruning (cost control).

resource "aws_ecr_repository" "api" {
  name                 = "platina-ai/api"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "platina-ecr-api"
  }
}

resource "aws_ecr_repository" "ingest" {
  name                 = "platina-ai/ingest"
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name = "platina-ecr-ingest"
  }
}

# Lifecycle Policy: Retain only the last 15 tagged images and purge untagged images older than 7 days
resource "aws_ecr_lifecycle_policy" "api_lifecycle" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 15 release images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "sha-"]
          countType     = "imageCountMoreThan"
          countNumber   = 15
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "ingest_lifecycle" {
  repository = aws_ecr_repository.ingest.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images older than 7 days"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 7
        }
        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2
        description  = "Keep last 15 release images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["v", "sha-"]
          countType     = "imageCountMoreThan"
          countNumber   = 15
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# --- IAM FOR CI/CD PIPELINE (GitHub Actions) ---

# Dedicated IAM user/role policy for GitHub Actions to authenticate, build, and push to ECR
resource "aws_iam_policy" "cicd_ecr_push" {
  name        = "platina-cicd-ecr-push-${var.environment}"
  description = "Allows CI/CD pipeline to push scanned container images to Platina AI ECR repositories"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetRepositoryPolicy",
          "ecr:DescribeRepositories",
          "ecr:ListImages",
          "ecr:DescribeImages",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = [
          aws_ecr_repository.api.arn,
          aws_ecr_repository.ingest.arn
        ]
      }
    ]
  })
}
