provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "__PROJECT_NAME__"
      ManagedBy = "terraform"
      Env       = "prod"
    }
  }
}
