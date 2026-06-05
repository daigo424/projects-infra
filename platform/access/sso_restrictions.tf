data "aws_iam_policy_document" "sso_ip_restriction" {
  statement {
    sid       = "DenyAllExceptFromSpecificIPs"
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]

    # IP はコンソール（OU root アカウント）で管理する（ignore_changes により Terraform は上書きしない）
    # 初回 apply 後に以下へ差し替える: 自宅グローバルIP・オフィスIP・VPN EIP（workloads/vpn output: vpn_public_ip）等
    # 0.0.0.0/0 は初回 apply 用プレースホルダー。NotIpAddress 条件が常に false になるため Deny は発動しない
    condition {
      test     = "NotIpAddress"
      variable = "aws:SourceIp"
      values   = ["0.0.0.0/0"]
    }

    condition {
      test     = "Bool"
      variable = "aws:ViaAWSService"
      values   = ["false"]
    }
  }
}

resource "aws_ssoadmin_permission_set_inline_policy" "sso_ip_restriction" {
  for_each           = local.used_permissions
  instance_arn       = var.identity_center_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.by_name[each.key].arn
  inline_policy      = data.aws_iam_policy_document.sso_ip_restriction.json

  lifecycle {
    ignore_changes = [inline_policy]
  }

  depends_on = [aws_ssoadmin_permission_set.by_name]
}
