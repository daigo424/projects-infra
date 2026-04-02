output "projects_ou_id" {
  value = aws_organizations_organizational_unit.projects.id
}

output "project_account_ids" {
  value = {
    for k, v in aws_organizations_account.projects : k => v.id
  }
}
