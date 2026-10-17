# 5. Terraform & Cloud Infrastructure Architecture Organization

Date: 2026-10-16

## Status
Accepted

## Context
Deploying the Platina AI production ecosystem onto Amazon Web Services (AWS) introduces multiple interconnected cloud concerns:
1. **Network Isolation:** Provisioning a 3-tier multi-AZ VPC segregating public ingress from application runtimes and database storage.
2. **Relational Vector Storage:** Running a managed PostgreSQL 16 instance with the `pgvector` extension, requiring zero-credential exposure in git.
3. **Container Compute & Packaging:** Maintaining private container registries (ECR) with immutable tags and hosting a certified Kubernetes cluster.
4. **Application Continuous Deployment:** Bridging the infrastructure provisioning phase with application runtime deployment (Helm) without brittle shell scripting.
5. **FinOps & Cost Ceilings:** Strictly controlling cloud expenditure with an aggressive monthly budget cap ($1.00 USD) and automated teardown capabilities for portfolio demonstrations.

## Decision

We structure our Terraform/OpenTofu infrastructure under `infra/terraform/` using a **modular, domain-segregated architecture**:

1. **State Isolation & Concurrency Locking (`backend.tf`, `versions.tf`):**
   - Remote state resides in an encrypted Amazon S3 bucket with server-side encryption (`AES256`).
   - Concurrency locking is enforced via an Amazon DynamoDB table (`platina-ai-terraform-locks`), preventing destructive simultaneous executions.

2. **Domain-Specific Declarative Files:**
   - `network.tf`: 3-tier multi-AZ VPC (`10.0.0.0/16`), public subnets for ingress, private app subnets for compute, and isolated DB subnets with security group chaining (`ALB` -> `App` -> `Database`).
   - `rds.tf`: Managed PostgreSQL 16 on AWS Graviton2 (`db.t4g.micro`) with `pgvector` support enabled via custom parameter groups. Secrets are dynamically generated (`random_password`) and deposited directly into AWS Secrets Manager.
   - `k3s.tf`: Certified Kubernetes cluster running on an EC2 Graviton instance (`t4g.small`), managed via Systems Manager Session Manager (no open SSH port 22).
   - `ecr.tf`: Private container repositories with tag immutability, automated CVE vulnerability scanning on push, and 7-day untagged layer lifecycle pruning.
   - `helm_release.tf`: Declarative Helm release dynamically injecting live RDS hostnames, credentials, and ECR repository URLs into the application chart.

3. **Strict FinOps Cost Controls (`budget.tf`, `destroy.sh`):**
   - Declared an `aws_budgets_budget` scoped to `user:Project$platina-ai` with a spending limit of **$1.00 USD**.
   - Automated alerts fire at **80% ($0.80 USD)** actual spend and **100% ($1.00 USD)** forecasted spend.
   - Automated teardown script (`destroy.sh`) allows tearing down all AWS resources in a single command, resetting ongoing idle costs to **$0.00**.

## Consequences

- **Positive:**
  - Complete separation of concerns: each infrastructure domain (`network`, `rds`, `compute`, `ecr`, `helm`) is decoupled and auditable.
  - Zero hardcoded credentials in source control.
  - Total expenditure is capped at $1.00 USD with proactive alerts, preventing surprise billing.
  - Automated teardown guarantees clean lifecycle management.

- **Trade-offs:**
  - Running k3s on a single EC2 Graviton node trades multi-master HA control planes for a >90% cost reduction, which is ideal for cost-conscious portfolio demonstrations.
