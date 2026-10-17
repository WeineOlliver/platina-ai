#!/usr/bin/env bash
# Tear-down script for Platina AI AWS Cloud Infrastructure
# Ensures complete resource destruction to guarantee zero ongoing idle costs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

echo "======================================================"
echo "⚠️  PLATINA AI CLOUD INFRASTRUCTURE TEAR-DOWN"
echo "======================================================"
echo "This will destroy all AWS resources created by OpenTofu/Terraform:"
echo " - Helm releases (platina-ai application pods & services)"
echo " - EC2 k3s cluster server & EBS storage"
echo " - AWS RDS PostgreSQL 16 instance & pgvector data"
echo " - AWS ECR container repositories (images pruned)"
echo " - AWS Secrets Manager secrets"
echo " - VPC, subnets, route tables, and security groups"
echo "======================================================"

read -p "Are you sure you want to completely destroy Platina AI cloud infrastructure? (yes/no): " CONFIRM
if [[ "${CONFIRM}" != "yes" ]]; then
  echo "Tear-down cancelled."
  exit 0
fi

echo "Initiating declarative teardown with OpenTofu..."

# Step 1: Ensure provider plugins are loaded
tofu init -backend=false

# Step 2: Execute destroy targeting all dependencies gracefully
tofu destroy -auto-approve

echo "✅ All Platina AI AWS cloud resources have been completely destroyed."
echo "Monthly cloud cost reset to $0.00."
