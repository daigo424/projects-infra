provider "aws" {
  region      = var.aws_region
  max_retries = 3
}
