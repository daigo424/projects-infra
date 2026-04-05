provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "uw-p-klein"
      ManagedBy = "terraform"
      Env       = "prod"
    }
  }
}
