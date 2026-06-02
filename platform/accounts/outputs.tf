output "workloads_ou_id" {
  value = aws_organizations_organizational_unit.workloads.id
}

output "workload_account_ids" {
  value = {
    for k, acc in aws_organizations_account.workloads : k => acc.id
  }
}
