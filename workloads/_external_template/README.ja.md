# External Terraform Template

projects-infra で管理されるワークロードのうち、Terraform コードを外部リポジトリで管理する場合のテンプレート。

## セットアップ手順

### 1. このディレクトリの内容を外部リポジトリにコピー

```
.github/workflows/terraform-plan.yml
.github/workflows/terraform-apply.yml
backend.hcl
```

### 2. GitHub リポジトリの variables を設定する

外部リポジトリの **Settings → Secrets and variables → Actions → Variables** で以下を追加する：

| Variable | 値 |
|---|---|
| `WORKLOAD_NAME` | projects-infra に登録されているワークロード名（例: `my-service`）。S3 state キーの一部として使用される。 |
| `PROD_ACCOUNT_ID` | prod 環境の AWS アカウント ID |
| `TEST_ACCOUNT_ID` | test 環境の AWS アカウント ID |

S3 バケット名は共通・固定のため `backend.hcl` の変更は不要。

prod のみの場合は `terraform-plan.yml` の matrix から `test` エントリを、`terraform-apply.yml` の case 文から `test` を削除する。

### 3. Terraform コードを配置する

デフォルトではリポジトリのルートに `.tf` ファイルを置く想定：

```
your-repo/
  main.tf
  variables.tf
  backend.hcl   ← ここに置く
  .github/workflows/
```

`terraform/` などのサブフォルダに置く場合は、両ワークフローの冒頭にある env 変数を変更する：

```yaml
env:
  TF_WORKING_DIR: "terraform"   # ← "." から変更
```

この場合 `backend.hcl` も同じフォルダ内に置く。

### 4. `variable "environment"` を追加する

`TF_VAR_environment` で注入されるため、Terraform コード内で以下を宣言する：

```hcl
variable "environment" {
  type = string
}
```

### 5. projects-infra 側の事前設定を確認する

外部リポジトリが `GitHubActionsWorkloadDeployRole` を assume するには、projects-infra 側で以下が必要：

- `create-workload-external` ワークフローでこのリポジトリを `terraform_repo` に指定してワークロードを作成済み
- これにより `metadata.json` に `additional_github_repos` が設定され、account-bootstrap が適用される
- account-bootstrap が apply 済みで `deploy_role_ready = true` になっている

### 6. （任意）ブランチ保護を設定する

**Settings → Rules** で `all-plans-passed` を必須ステータスチェックに追加すると、plan 失敗時にマージをブロックできる。

## S3 ステートキー

state は projects-infra と共有の S3 バケットに以下のキーで保存される：

```
workloads/<WORKLOAD_NAME>/prod/additional_github_repos/<org>/<repo>/terraform.tfstate
workloads/<WORKLOAD_NAME>/test/additional_github_repos/<org>/<repo>/terraform.tfstate
```

## ワークフローの動作

| ワークフロー | トリガー | 内容 |
|---|---|---|
| `terraform-plan` | PR 作成・更新時 | prod/test を並列で plan、結果を PR コメントに投稿 |
| `terraform-plan` | 手動（workflow_dispatch） | 全環境を強制 plan、結果を job summary で確認可能 |
| `terraform-apply` | 手動（workflow_dispatch） | 環境を選択して apply |
