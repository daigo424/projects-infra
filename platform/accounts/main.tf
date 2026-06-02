locals {
  metadata_files = fileset("${path.root}/../../workloads", "*/metadata.json")

  workload_configs = {
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../workloads/${rel}")).workload_name => jsondecode(file("${path.root}/../../workloads/${rel}"))
    if !startswith(rel, "_template/")
  }

  env_accounts = {
    for pair in flatten([
      for workload_name, config in local.workload_configs : [
        for env_name, env_config in config.environments : {
          key          = "${workload_name}-${env_name}"
          display_name = env_name == "prod" ? "PROD-${workload_name}" : "TEST-${workload_name}"
          email        = env_config.account_email
        }
      ]
    ]) : pair.key => pair
  }
}

data "aws_organizations_organization" "org" {}

resource "aws_organizations_organizational_unit" "workloads" {
  name      = var.workloads_ou_name
  parent_id = data.aws_organizations_organization.org.roots[0].id
}

moved {
  from = aws_organizations_organizational_unit.projects
  to   = aws_organizations_organizational_unit.workloads
}

resource "aws_organizations_account" "workloads" {
  for_each = local.env_accounts

  name      = each.value.display_name
  email     = each.value.email
  parent_id = aws_organizations_organizational_unit.workloads.id

  lifecycle {
    prevent_destroy = true
  }
}

moved {
  from = aws_organizations_account.projects
  to   = aws_organizations_account.workloads
}
