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
  default = "GitHubActionsWorkloadDeployRole"
}

variable "oidc_provider_arn" {
  description = "Optional OIDC provider ARN. Leave null to create a GitHub OIDC provider in this account."
  type        = string
  default     = null
}

variable "additional_github_repos" {
  description = "Additional GitHub repos to trust for OIDC (format: org/repo). Set when Terraform is managed in a separate repo."
  type        = list(string)
  default     = []
}
