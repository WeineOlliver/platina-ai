# Remote backend definition for production state isolation in AWS S3 with DynamoDB locking.
# In local/sandbox development, Terraform defaults to local state if S3 is unconfigured.
terraform {
  backend "s3" {
    bucket         = "platina-ai-terraform-state-590184022238"
    key            = "platina-ai/prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "platina-ai-terraform-locks"
  }
}
