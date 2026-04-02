output "github_oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.github.arn
}

output "platform_role_arn" {
  value = module.platform_role.role_arn
}
