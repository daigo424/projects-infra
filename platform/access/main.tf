locals {
  metadata_files = fileset("${path.root}/../../projects", "*/metadata.json")

  raw_project_configs = [
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../projects/${rel}"))
    if !startswith(rel, "_template/")
  ]

  env_configs = {
    for pair in flatten([
      for config in local.raw_project_configs : [
        for env_name, env_config in config.environments : {
          key        = "${config.project_name}-${env_name}"
          account_id = try(env_config.account_id, "")
          enabled    = try(env_config.enabled_for_access, false)
        }
      ]
    ]) : pair.key => pair
    if try(pair.enabled, false) && can(regex("^[0-9]{12}$", pair.account_id))
  }
}

resource "aws_ssoadmin_permission_set" "admin" {
  instance_arn     = var.identity_center_instance_arn
  name             = var.permission_set_name
  session_duration = "PT4H"
}

resource "aws_ssoadmin_managed_policy_attachment" "admin" {
  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.admin.arn
  managed_policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

resource "aws_ssoadmin_account_assignment" "project_access" {
  for_each = local.env_configs

  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.admin.arn

  principal_id   = var.principal_group_id
  principal_type = "GROUP"

  target_id   = each.value.account_id
  target_type = "AWS_ACCOUNT"
}
