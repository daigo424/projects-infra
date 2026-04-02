resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

module "platform_role" {
  source = "../modules/github_oidc_role"

  name              = var.role_name
  oidc_provider_arn = aws_iam_openid_connect_provider.github.arn
  github_org        = var.github_org
  github_repo       = var.github_repo

  inline_policy_json = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "organizations:*",
          "sso:*",
          "identitystore:*",
          "iam:*",
          "sts:GetCallerIdentity",
          "s3:*"
        ]
        Resource = "*"
      }
    ]
  })
}
