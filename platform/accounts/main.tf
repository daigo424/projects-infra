locals {
  metadata_files = fileset("${path.root}/../../projects", "*/metadata.json")

  project_configs = {
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../projects/${rel}")).project_name => jsondecode(file("${path.root}/../../projects/${rel}"))
    if !startswith(rel, "_template/")
  }
}

data "aws_organizations_organization" "org" {}

resource "aws_organizations_organizational_unit" "projects" {
  name      = var.projects_ou_name
  parent_id = data.aws_organizations_organization.org.roots[0].id
}

resource "aws_organizations_account" "projects" {
  for_each = local.project_configs

  name      = each.value.display_name
  email     = each.value.account_email
  parent_id = aws_organizations_organizational_unit.projects.id

  lifecycle {
    prevent_destroy = true
  }
}
