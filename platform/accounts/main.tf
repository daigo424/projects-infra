locals {
  metadata_files = fileset("${path.root}/../../projects", "*/metadata.json")

  project_configs = {
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../projects/${rel}")).project_name => jsondecode(file("${path.root}/../../projects/${rel}"))
    if !startswith(rel, "_template/")
  }

  env_accounts = {
    for pair in flatten([
      for project_name, config in local.project_configs : [
        for env_name, env_config in config.environments : {
          key          = "${project_name}-${env_name}"
          display_name = env_name == "prod" ? "PROD-${project_name}" : "TEST-${project_name}"
          email        = env_config.account_email
        }
      ]
    ]) : pair.key => pair
  }
}

data "aws_organizations_organization" "org" {}

resource "aws_organizations_organizational_unit" "projects" {
  name      = var.projects_ou_name
  parent_id = data.aws_organizations_organization.org.roots[0].id
}

resource "aws_organizations_account" "projects" {
  for_each = local.env_accounts

  name      = each.value.display_name
  email     = each.value.email
  parent_id = aws_organizations_organizational_unit.projects.id

  lifecycle {
    prevent_destroy = true
  }
}
