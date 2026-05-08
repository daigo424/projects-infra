resource "aws_iam_openid_connect_provider" "github" {
  count = var.oidc_provider_arn == null ? 1 : 0

  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  effective_oidc_provider_arn = var.oidc_provider_arn != null ? var.oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn

  trusted_repos = concat(["${var.github_org}/${var.github_repo}"], var.additional_github_repos)
  trusted_subs = flatten([
    for repo in local.trusted_repos : [
      "repo:${repo}:ref:refs/heads/main",
      "repo:${repo}:pull_request",
      "repo:${repo}:ref:refs/tags/*",
    ]
  ])
}

data "aws_iam_policy_document" "assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.effective_oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = local.trusted_subs
    }
  }
}

resource "aws_iam_role" "deploy" {
  name               = var.github_actions_role_name
  assume_role_policy = data.aws_iam_policy_document.assume.json
}

resource "aws_iam_role_policy_attachment" "deploy_admin" {
  role       = aws_iam_role.deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
