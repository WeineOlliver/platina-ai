# 4. Kubernetes Infrastructure Decision: Amazon EKS vs. Lightweight k3s / Kind

Date: 2026-10-16

## Status
Accepted

## Context
Platina AI requires a container orchestrator capable of hosting a multi-tier AI application:
1. Fastify Node.js API with real-time SSE streaming.
2. FastAPI Python microservice performing semantic chunking and pgvector search queries.
3. PostgreSQL database with vector extensions and persistent storage volume attachments.

The target infrastructure must satisfy two competing constraints:
- **Production Enterprise Readiness:** Demonstrating production-grade cloud orchestration patterns (IAM Roles for Service Accounts / IRSA, Managed Node Groups, Multi-AZ high availability) expected in Senior Remote Software Engineering interviews.
- **Cost Efficiency for Personal Portfolio:** Avoiding prohibitive idle control-plane costs ($73/month flat fee per Amazon EKS cluster before compute/node charges) during continuous development and demonstration phases.

## Decision
We adopt a **Decoupled Helm-First Infrastructure Strategy** comparing Amazon EKS and k3s/Kind:

1. **Target Abstraction Layer (Helm):**
   - We package the entire microservice ecosystem into an environment-agnostic Helm chart (`infra/helm/platina-ai`).
   - All environment-specific behaviors (Ingress controllers, StorageClass types, NodePorts vs. AWS Application Load Balancers) are parameterized via `values.yaml` and overlay files (`values.local.yaml`, `values.prod.yaml`).

2. **Local & Development Runtime (Kind / k3s):**
   - For day-to-day development, integration tests, and cost-free live demos, we run Kubernetes on Kind (Kubernetes in Docker) and lightweight k3s.
   - Storage uses local `standard` hostPath provisioners; traffic enters via host port mappings (`30080` NodePort, `8080` Ingress).
   - Control plane cost: **$0.00**.

3. **Cloud Target Topology (Amazon EKS):**
   - For enterprise staging/production deployments, the Helm chart deploys to Amazon EKS managed via Terraform.
   - Storage leverages AWS EBS CSI Driver (`gp3` StorageClass with volume snapshots).
   - Ingress utilizes AWS Load Balancer Controller provisioning an Application Load Balancer (ALB) with SSL/TLS termination via ACM.
   - Pod identity leverages IAM Roles for Service Accounts (IRSA) for fine-grained AWS resource access rather than long-lived hardcoded IAM credentials.

## Trade-off Analysis

| Metric / Dimension | Amazon EKS | k3s / Kind |
| :--- | :--- | :--- |
| **Control Plane Cost** | ~$73.00/month flat fee | $0.00 (Runs on local Docker or single EC2 spot instance) |
| **Operational Overhead** | Low (AWS manages control plane upgrades, etcd backups, and HA) | Higher for multi-node production; minimal for single-node development |
| **Storage CSI** | Amazon EBS CSI / EFS CSI | HostPath / local-path-provisioner |
| **Identity & Access** | AWS IAM / IRSA native | Native K8s RBAC + ServiceAccount tokens |
| **Scaling Dynamics** | Cluster Autoscaler / Karpenter + HPA | Metrics-server + HPA within fixed compute boundary |

## Consequences
- **Positive:**
  - Zero cloud vendor lock-in: our workload deploys identically to local Kind, single-node k3s on an affordable EC2 spot instance, or full-scale multi-AZ Amazon EKS.
  - Zero idle development cost while demonstrating deep enterprise Kubernetes competency.
  - One-line deployment via `helm install platina-ai infra/helm/platina-ai`.
