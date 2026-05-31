variable "aws_region" {
  type = string
}

variable "identity_center_instance_arn" {
  type = string
}

variable "identity_store_id" {
  type        = string
  description = "IAM Identity Center の Identity Store ID (例: d-1234567890). コンソール > IAM Identity Center > Settings で確認できる"
}
