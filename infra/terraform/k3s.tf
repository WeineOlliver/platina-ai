# IAM Role for k3s EC2 Node to access ECR and Secrets Manager
resource "aws_iam_role" "k3s_node" {
  name = "platina-k3s-node-role-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "platina-k3s-node-role"
  }
}

# Attach AmazonSSMManagedInstanceCore for secure SSH-less Systems Manager Session Manager access
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.k3s_node.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# Custom policy for ECR read and Secrets Manager access
resource "aws_iam_policy" "k3s_permissions" {
  name        = "platina-k3s-permissions-${var.environment}"
  description = "Allows k3s node to pull from ECR and read Platina AI database secrets"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = [aws_secretsmanager_secret.db_credentials.arn]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "k3s_custom" {
  role       = aws_iam_role.k3s_node.name
  policy_arn = aws_iam_policy.k3s_permissions.arn
}

resource "aws_iam_instance_profile" "k3s_profile" {
  name = "platina-k3s-instance-profile-${var.environment}"
  role = aws_iam_role.k3s_node.name
}

# Latest Amazon Linux 2023 AMI for ARM64 Graviton
data "aws_ami" "amazon_linux_arm" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-arm64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# EC2 Instance hosting the lightweight k3s Kubernetes cluster
resource "aws_instance" "k3s_server" {
  ami                  = data.aws_ami.amazon_linux_arm.id
  instance_type        = "t4g.small" # 2 vCPU, 2GB RAM ARM64 Graviton (~$0.0168/hour)
  subnet_id            = aws_subnet.public[0].id
  vpc_security_group_ids = [aws_security_group.app.id]
  iam_instance_profile = aws_iam_instance_profile.k3s_profile.name

  associate_public_ip_address = true

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = <<-EOF
              #!/bin/bash
              set -ex

              # Update system packages
              dnf update -y
              dnf install -y curl tar gzip jq

              # Install lightweight certified k3s Kubernetes distribution
              curl -sfL https://get.k3s.io | sh -s - \
                --write-kubeconfig-mode 644 \
                --tls-san $(curl -s http://169.254.169.254/latest/meta-data/public-ipv4) \
                --disable traefik \
                --node-label app.kubernetes.io/part-of=platina-ai

              # Verify k3s service status
              systemctl enable k3s
              systemctl status k3s || true
              EOF

  tags = {
    Name = "platina-k3s-server"
    Role = "kubernetes-control-plane"
  }
}
