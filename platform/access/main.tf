locals {
  metadata_files = fileset("${path.root}/../../projects", "*/metadata.json")

  raw_project_configs = [
    for rel in local.metadata_files :
    jsondecode(file("${path.root}/../../projects/${rel}"))
    if !startswith(rel, "_template/")
  ]

  # platform/users.json: 全ユーザーの正規リスト
  platform_users = jsondecode(file("${path.root}/../users.json"))
  users_by_email = { for u in local.platform_users : u.email => u }

  # 全 project × env × member の組み合わせ展開
  member_assignments = {
    for pair in flatten([
      for config in local.raw_project_configs : [
        for env_name, env_config in config.environments : [
          for member in try(config.members, []) : {
            key        = "${config.project_name}-${env_name}-${member.email}"
            account_id = env_config.account_id
            email      = member.email
            permission = try(member.permissions[env_name], null)
          }
          if try(env_config.enabled_for_access, false)
          && can(regex("^[0-9]{12}$", env_config.account_id))
          && try(member.permissions[env_name], null) != null
        ]
      ]
    ]) : pair.key => pair
  }

  used_permissions = toset([for a in local.member_assignments : a.permission])

  # サポートする permission set 名 → managed policy ARN
  # 追加したい場合はここに足す
  permission_policy_arns = {
    "AdministratorAccess" = "arn:aws:iam::aws:policy/AdministratorAccess"
    "ReadOnlyAccess"      = "arn:aws:iam::aws:policy/ReadOnlyAccess"
    "PowerUserAccess"     = "arn:aws:iam::aws:policy/PowerUserAccess"
  }
}

# IAM Identity Center ユーザー
# 新規ユーザーはここで作成 → AWS がメール招待を自動送信する
resource "aws_identitystore_user" "users" {
  for_each          = local.users_by_email
  identity_store_id = var.identity_store_id

  display_name = each.value.display_name
  user_name    = each.value.username

  name {
    given_name  = each.value.given_name
    family_name = each.value.family_name
  }

  emails {
    value   = each.key
    type    = "work"
    primary = true
  }
}

# 実際に使われている permission set だけ動的に作成
resource "aws_ssoadmin_permission_set" "by_name" {
  for_each         = local.used_permissions
  instance_arn     = var.identity_center_instance_arn
  name             = each.key
  session_duration = "PT4H"
}

resource "aws_ssoadmin_managed_policy_attachment" "by_name" {
  for_each           = local.used_permissions
  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.by_name[each.key].arn
  managed_policy_arn = local.permission_policy_arns[each.key]

  depends_on = [aws_ssoadmin_permission_set.by_name]
}

# ユーザー × アカウント × permission set のアサイン
resource "aws_ssoadmin_account_assignment" "member_access" {
  for_each           = local.member_assignments
  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.by_name[each.value.permission].arn

  principal_id   = aws_identitystore_user.users[each.value.email].user_id
  principal_type = "USER"

  target_id   = each.value.account_id
  target_type = "AWS_ACCOUNT"
}
