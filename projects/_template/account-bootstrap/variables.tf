variable "aws_region" {
  type = string
}

variable "github_org" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "github_actions_role_name" {
  type    = string
  default = "GitHubActionsProjectDeployRole"
}

variable "oidc_provider_arn" {
  description = "Optional OIDC provider ARN. Leave null to create a GitHub OIDC provider in this account."
  type        = string
  default     = null
}
