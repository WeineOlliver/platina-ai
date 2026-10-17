# Availability zones data source
data "aws_availability_zones" "available" {
  state = "available"
}

# Dedicated VPC for Platina AI
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "platina-vpc-${var.environment}"
  }
}

# Internet Gateway for public ingress
resource "aws_internet_gateway" "gw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "platina-igw-${var.environment}"
  }
}

# Public Subnets (for ALB / Ingress)
resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 4, count.index)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name                     = "platina-subnet-public-${data.aws_availability_zones.available.names[count.index]}"
    "kubernetes.io/role/elb" = "1"
  }
}

# Private Application Subnets (for Compute / Kubernetes Nodes / Pods)
resource "aws_subnet" "private_app" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 2)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name                              = "platina-subnet-app-${data.aws_availability_zones.available.names[count.index]}"
    "kubernetes.io/role/internal-elb" = "1"
  }
}

# Private Database Subnets (isolated for RDS pgvector)
resource "aws_subnet" "private_db" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 4, count.index + 4)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = {
    Name = "platina-subnet-db-${data.aws_availability_zones.available.names[count.index]}"
  }
}

# Public Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.gw.id
  }

  tags = {
    Name = "platina-rt-public"
  }
}

# Public Route Table Associations
resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# DB Subnet Group for RDS
resource "aws_db_subnet_group" "main" {
  name        = "platina-db-subnet-group-${var.environment}"
  subnet_ids  = aws_subnet.private_db[*].id
  description = "Isolated private subnets for PostgreSQL RDS pgvector instance"

  tags = {
    Name = "platina-db-subnet-group"
  }
}

# --- SECURITY GROUPS ---

# 1. Security Group for Public Application Load Balancer
resource "aws_security_group" "alb" {
  name        = "platina-sg-alb-${var.environment}"
  description = "Allows incoming HTTP/HTTPS traffic to Platina AI Load Balancer"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "Allow HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "Allow HTTPS from internet"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow outbound to app workloads"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "platina-sg-alb"
  }
}

# 2. Security Group for Application Compute / Kubernetes Nodes
resource "aws_security_group" "app" {
  name        = "platina-sg-app-${var.environment}"
  description = "Allows traffic between ALB and application pods"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow traffic from ALB on NodePort/container ports"
    from_port       = 3000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Allow pod-to-pod communication within cluster"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    description = "Allow outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "platina-sg-app"
  }
}

# 3. Security Group for PostgreSQL Database (Least Privilege)
resource "aws_security_group" "db" {
  name        = "platina-sg-db-${var.environment}"
  description = "Restricts PostgreSQL port 5432 strictly to application compute"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow PostgreSQL access strictly from app workloads"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }

  egress {
    description = "Deny default egress"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
  }

  tags = {
    Name = "platina-sg-db"
  }
}
