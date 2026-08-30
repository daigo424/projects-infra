data "aws_iam_policy_document" "sso_ip_restriction" {
  statement {
    sid       = "DenyAllExceptFromSpecificIPs"
    effect    = "Deny"
    actions   = ["*"]
    resources = ["*"]

    # 実際のIPに差し替える: 自宅グローバルIP・オフィスIP・VPN EIP など
    # プレースホルダー: 0.0.0.0/0（全IPv4）と ::/0（全IPv6）を両方指定することで
    # NotIpAddress 条件が常に false になり Deny は発動しない
    condition {
      test     = "NotIpAddress"
      variable = "aws:SourceIp"
      values   = ["0.0.0.0/0", "::/0"]
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

  depends_on = [aws_ssoadmin_permission_set.by_name]
}
