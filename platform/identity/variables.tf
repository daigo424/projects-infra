variable "aws_region" {
  type = string
}

variable "github_org" {
  type = string
}

variable "github_repo" {
  type = string
}

variable "role_name" {
  type    = string
  default = "GitHubActionsPlatformRole"
}
