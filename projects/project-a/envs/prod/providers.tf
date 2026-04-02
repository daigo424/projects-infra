provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "project-a"
      ManagedBy = "terraform"
      Env       = "prod"
    }
  }
}
