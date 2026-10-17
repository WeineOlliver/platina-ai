provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "platina-ai"
      Environment = var.environment
      ManagedBy   = "terraform"
      Repository  = "https://github.com/WeineOlliver/platina-ai"
    }
  }
}
