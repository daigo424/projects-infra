# Replace PROJECT_NAME and ACCOUNT_ID with actual values
bucket   = "daigo424-aws-tfstate-20260402"
key      = "projects/PROJECT_NAME/prod/terraform.tfstate"
region   = "ap-northeast-1"
role_arn = "arn:aws:iam::ACCOUNT_ID:role/GitHubActionsProjectDeployRole"
encrypt  = true
