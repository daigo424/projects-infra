# Projects Infra

AWS マルチアカウント Terraform モノレポ。

## 📁 ディレクトリ構成

```
platform/                     # 管理アカウントのリソース
  bootstrap/                  # S3 ステートバケット・アクセスポリシー
  accounts/                   # AWS Organizations アカウント作成
  identity/                   # GitHub OIDC プロバイダー（管理アカウント）
  access/                     # IAM Identity Center 設定
  modules/github_oidc_role/   # 再利用可能な OIDC ロールモジュール
  metadata.json               # 管理アカウント設定

projects/                     # プロジェクトごとの AWS アカウント
  _template/                  # 新規プロジェクトのテンプレート（apply 不可）
  _external_template/         # 外部リポジトリ管理プロジェクト用テンプレート
  <project-name>/
    account-bootstrap/        # OIDC プロバイダー・デプロイロール作成
    envs/                     # インフラリソース（環境は var.environment で切替）
    modules/                  # プロジェクト固有モジュール
    metadata.json             # プロジェクト設定

.github/
  workflows/
    terraform-plan.yml        # PR 時に変更対象を自動検出して plan
    terraform-apply.yml       # 手動 dispatch で apply
  scripts/
    create_project.py         # プロジェクト作成スクリプト
    discover_targets.py       # Terraform ターゲット自動検出
    filter_changed_targets.py # 変更差分によるターゲット絞り込み
    resolve_role_arn.py       # ターゲットに応じた IAM ロール解決
```

---

## ⚙️ GitHub Actions の動作

### Plan（PR 時）

`platform/**` または `projects/**` の変更を含む PR を作成すると、変更されたターゲットに対して `terraform plan` が自動実行される。

### Apply（手動）

`terraform-apply.yml` を workflow dispatch で実行。`target_name` にターゲット名を指定する（例: `project-a-prod`、`project-a-test-account-bootstrap`）。

### 認証（OIDC）

静的な AWS 認証情報は使わず GitHub OIDC で認証する。ターゲットの種別に応じて以下のロールを assume する。

| ターゲット種別 | 使用ロール |
|---|---|
| `platform`, `platform-bootstrap` | 管理アカウントの `GitHubActionsPlatformRole` |
| `project-bootstrap`（deploy_role_ready=false） | ① `GitHubActionsPlatformRole` → ② `OrganizationAccountAccessRole`（プロジェクトアカウント）へ chain |
| `project-bootstrap`（deploy_role_ready=true） | プロジェクトアカウントの `GitHubActionsProjectDeployRole` |
| `project` | プロジェクトアカウントの `GitHubActionsProjectDeployRole` |

---

## 🗂 Terraform 管理の 2 つのモード

### 本リポジトリ管理（デフォルト）

`envs/` を本リポジトリに置き、GitHub Actions で plan/apply する。`environment` 変数は CI 実行時に `TF_VAR_environment` として注入される。

### 外部リポジトリ管理

`metadata.json` に `terraform_repo` を指定すると、本リポジトリの GitHub Actions は `envs/` を対象外とし、指定リポジトリ側で管理する。

```json
{
  "terraform_repo": "org/external-repo-name"
}
```

外部リポジトリ側のセットアップは `projects/_external_template/` を参照。

account-bootstrap の OIDC ロールに外部リポジトリを追加で信頼させるには `terraform.auto.tfvars` に以下を追加して `account-bootstrap` を再 apply する。

```hcl
additional_github_repos = ["org/external-repo-name"]
```

---

## ➕ プロジェクト追加

```bash
py .github/scripts/create_project.py <project-name> <email> <vpc-cidr> [environments]
# 例（prod のみ）:     py .github/scripts/create_project.py my-project me@example.com 10.0.0.0/16
# 例（prod + test）:   py .github/scripts/create_project.py my-project me@example.com 10.0.0.0/16 prod,test
```

各環境について以下の処理が実行される:

1. `_template` からプロジェクトディレクトリを生成
2. `platform/accounts` apply → AWS アカウント作成（`PROD-<project>` / `TEST-<project>`）
3. `metadata.json` に `account_id` を記録
4. `platform/bootstrap` apply → S3 アクセスポリシー更新
5. `platform/access` apply → IAM Identity Center 設定
6. `account-bootstrap` apply → OIDC プロバイダー・デプロイロール作成（GitHub Actions が `OrganizationAccountAccessRole` へ role-chaining して実行）
7. `metadata.json` に `deploy_role_ready=true` を記録
8. `platform/bootstrap` apply → デプロイロール用 S3 ポリシー追加
9. （任意）`envs` apply（`TF_VAR_environment=<env>`）→ インフラデプロイ

---

## 🗃 S3 ステート管理

- 管理アカウントの S3 バケットに全ステートを集約
- 環境ごとにプレフィックスで分離: `projects/<project-name>/<env>/*`
- `metadata.json` を元に自動でバケットポリシーを管理

---

## ⚙️ 初回セットアップ（一度だけ）

```bash
cd platform/bootstrap && terraform apply
cd platform/identity  && terraform apply
cd platform/accounts  && terraform apply
cd platform/access    && terraform apply
```
