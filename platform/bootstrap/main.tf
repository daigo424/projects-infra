locals {
  metadata_files = fileset("${path.root}/../../workloads", "*/metadata.json")

  raw_workload_configs = [
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../workloads/${rel}"))
    if !startswith(rel, "_template/")
  ]

  env_configs = {
    for pair in flatten([
      for config in local.raw_workload_configs : [
        for env_name, env_config in config.environments : {
          key               = "${config.workload_name}-${env_name}"
          workload_name     = config.workload_name
          env_name          = env_name
          account_id        = try(env_config.account_id, "")
          role_name         = config.role_name
          deploy_role_ready = try(env_config.deploy_role_ready, false)
          state_prefix      = "workloads/${config.workload_name}/${env_name}"
        }
      ]
    ]) : pair.key => pair
    if can(regex("^[0-9]{12}$", pair.account_id))
  }

  env_role_principals = {
    for key, env in local.env_configs :
    key => compact([
      "arn:aws:iam::${env.account_id}:role/OrganizationAccountAccessRole",
      env.deploy_role_ready
      ? "arn:aws:iam::${env.account_id}:role/${env.role_name}"
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
      type = "AWS"
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
    for_each = local.env_configs
    content {
      sid    = "Allow${replace(statement.key, "-", "")}ListBucket"
      effect = "Allow"

      principals {
        type        = "AWS"
        identifiers = local.env_role_principals[statement.key]
      }

      actions   = ["s3:ListBucket"]
      resources = [aws_s3_bucket.tfstate.arn]

      condition {
        test     = "StringLike"
        variable = "s3:prefix"
        values   = ["${statement.value.state_prefix}/*"]
      }
    }
  }

  dynamic "statement" {
    for_each = local.env_configs
    content {
      sid    = "Allow${replace(statement.key, "-", "")}ObjectAccess"
      effect = "Allow"

      principals {
        type        = "AWS"
        identifiers = local.env_role_principals[statement.key]
      }

      actions = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ]

      resources = [
        "${aws_s3_bucket.tfstate.arn}/${statement.value.state_prefix}/*"
      ]
    }
  }
}

resource "aws_s3_bucket_policy" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  policy = data.aws_iam_policy_document.tfstate_bucket_policy.json
}
