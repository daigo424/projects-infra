locals {
  metadata_files = fileset("${path.root}/../../projects", "*/metadata.json")

  raw_project_configs = [
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../projects/${rel}"))
    if !startswith(rel, "_template/")
  ]

  project_configs = {
    for p in local.raw_project_configs :
    p.project_name => p
    if can(regex("^[0-9]{12}$", p.account_id))
  }

  project_role_principals = {
    for project_name, project in local.project_configs :
    project_name => compact([
      "arn:aws:iam::${project.account_id}:role/OrganizationAccountAccessRole",
      try(project.deploy_role_ready, false)
        ? "arn:aws:iam::${project.account_id}:role/${try(project.role_name, "GitHubActionsProjectDeployRole")}"
        : null
    ])
  }
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket" "tfstate" {
  bucket = var.state_bucket

  tags = {
    Name      = var.state_bucket
    ManagedBy = "terraform"
  }
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

data "aws_iam_policy_document" "tfstate_bucket_policy" {
  statement {
    sid    = "AllowManagementAccountAccess"
    effect = "Allow"

    principals {
      type        = "AWS"
      identifiers = [
        "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
      ]
    }

    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.tfstate.arn,
      "${aws_s3_bucket.tfstate.arn}/*"
    ]
  }

  dynamic "statement" {
    for_each = local.project_configs
    content {
      sid    = "Allow${replace(statement.key, "-", "")}ListBucket"
      effect = "Allow"

      principals {
        type        = "AWS"
        identifiers = local.project_role_principals[statement.key]
      }

      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.tfstate.arn]

      condition {
        test     = "StringLike"
        variable = "s3:prefix"
        values = [
          "projects/${statement.key}/*"
        ]
      }
    }
  }

  dynamic "statement" {
    for_each = local.project_configs
    content {
      sid    = "Allow${replace(statement.key, "-", "")}ObjectAccess"
      effect = "Allow"

      principals {
        type        = "AWS"
        identifiers = local.project_role_principals[statement.key]
      }

      actions = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ]

      resources = [
        "${aws_s3_bucket.tfstate.arn}/projects/${statement.key}/*"
      ]
    }
  }
}

resource "aws_s3_bucket_policy" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  policy = data.aws_iam_policy_document.tfstate_bucket_policy.json
}