provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Workload  = var.workload_name
      ManagedBy = "terraform"
      Env       = var.environment
    }
  }
}
