variable "aws_region" {
  description = "AWS region for the Terraform state bucket."
  type        = string
}

variable "state_bucket" {
  description = "Globally unique S3 bucket name for Terraform state."
  type        = string
}
