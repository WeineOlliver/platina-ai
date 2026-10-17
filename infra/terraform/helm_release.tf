# Helm and Kubernetes provider configurations wired to the AWS Kubernetes cluster
# Deploys the Platina AI application chart onto the cloud environment declaratively.

provider "helm" {
  kubernetes {
    host                   = "https://${aws_instance.k3s_server.public_ip}:6443"
    insecure               = true
  }
}

# Declarative Application Release using the local chart and production AWS overlay
resource "helm_release" "platina_ai" {
  name             = "platina-ai"
  chart            = "${path.module}/../helm/platina-ai"
  namespace        = "platina"
  create_namespace = true
  timeout          = 300
  wait             = false # Avoid blocking pipeline if cluster is bootstrapping

  values = [
    file("${path.module}/../helm/platina-ai/values.aws.yaml")
  ]

  # Dynamic cloud overrides injecting live Terraform outputs directly into the Helm chart
  set {
    name  = "api.image.repository"
    value = aws_ecr_repository.api.repository_url
  }

  set {
    name  = "ingest.image.repository"
    value = aws_ecr_repository.ingest.repository_url
  }

  set {
    name  = "postgres.host"
    value = aws_db_instance.postgres.address
  }

  set {
    name  = "postgres.auth.database"
    value = var.db_name
  }

  set {
    name  = "postgres.auth.username"
    value = var.db_username
  }

  set_sensitive {
    name  = "postgres.auth.password"
    value = random_password.db_password.result
  }

  depends_on = [
    aws_instance.k3s_server,
    aws_db_instance.postgres,
    aws_ecr_repository.api,
    aws_ecr_repository.ingest
  ]
}
