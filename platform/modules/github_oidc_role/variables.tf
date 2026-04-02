variable "name" {
  type = string
}

variable "oidc_provider_arn" {
  type = string
}

variable "github_org" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "inline_policy_json" {
  type    = string
  default = null
}
