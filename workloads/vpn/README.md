# vpn workload

Tailscale を使った VPN サーバー。サブネットルーター兼 Exit Node として機能する。

- **インスタンス**: t4g.nano (Ubuntu 24.04 ARM64)
- **リージョン**: ap-northeast-1a
- **広告ルート**: `10.64.48.0/20`（vpn workload の VPC CIDR）

---

## EC2 の起動・停止

`workloads/vpn/terraform.auto.tfvars` の `create_compute` で EC2・EIP を一括制御できる。VPC・Subnet・IGW・SG・IAM Role は常時維持される（課金なし）。

### 停止（EC2・EIP を削除）

```hcl
# terraform.auto.tfvars
create_compute = false
```

GitHub Actions → **terraform-apply** → `workflow_dispatch`
- `target_name`: `workloads/vpn:prod`

### 起動（EC2・EIP を再作成）

```hcl
# terraform.auto.tfvars
create_compute = true
```

同様に terraform-apply を実行。

---

## 起動後にやること

EC2 が立ち上がっても、以下を完了しないと VPN として使えない。

### 1. Tailscale 管理コンソールでノードを確認

前回のインスタンスがオフラインノードとして残っている場合は削除する。
<https://login.tailscale.com/admin/machines>

### 2. サブネットルートを承認

新しいノードの `10.64.48.0/20` ルートを承認する。

Tailscale 管理コンソール → Machines → 該当ノード → Edit route settings → `10.64.48.0/20` を有効化

### 3. SSO の許可 IP リストを更新（使用している場合）

EIP は再作成のたびに変わる。IAM Identity Center の permission set インラインポリシーに VPN の EIP を追加している場合は更新する。

新しい EIP は terraform output または AWS コンソールで確認できる。

---

## Tailscale auth key について

SSM Parameter Store `/vpn/tailscale-auth-key` に保存されているキーが **Reusable** である必要がある。One-time キーの場合、再作成時の `tailscale up` が失敗する。

確認・変更: <https://login.tailscale.com/admin/settings/keys>

キーを更新した場合は SSM Parameter Store も更新する。

```bash
aws ssm put-parameter \
  --name "/vpn/tailscale-auth-key" \
  --value "<new-auth-key>" \
  --type SecureString \
  --overwrite \
  --region ap-northeast-1
```
