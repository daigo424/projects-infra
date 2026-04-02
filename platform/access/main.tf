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
    if try(p.enabled_for_access, false) && can(regex("^[0-9]{12}$", p.account_id))
  }
}

resource "aws_ssoadmin_permission_set" "developer" {
  instance_arn     = var.identity_center_instance_arn
  name             = var.permission_set_name
  session_duration = "PT4H"
}

resource "aws_ssoadmin_managed_policy_attachment" "poweruser" {
  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.developer.arn
  managed_policy_arn = "arn:aws:iam::aws:policy/PowerUserAccess"
}

resource "aws_ssoadmin_account_assignment" "project_access" {
  for_each = local.project_configs

  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.developer.arn

  principal_id   = var.principal_group_id
  principal_type = "GROUP"

  target_id   = each.value.account_id
  target_type = "AWS_ACCOUNT"
}
