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
    terraform-plan.yml           # PR 時に変更対象を自動検出して plan
    terraform-apply.yml          # 手動 dispatch で apply
    create-project.yml           # プロジェクト追加 PR 作成（本リポジトリ管理）
    create-project-external.yml  # プロジェクト追加 PR 作成（外部リポジトリ管理）
  scripts/
    new_project.py            # テンプレートからプロジェクトディレクトリを生成
    discover_targets.py       # Terraform ターゲット自動検出
    filter_changed_targets.py # 変更差分によるターゲット絞り込み
    resolve_role_arn.py       # ターゲットに応じた IAM ロール解決

scripts/
  allocate_cidr.py            # VPC CIDR 払い出しツール（Tier別連番割り当て）

.repo-meta/
  used_vpc_cidrs.csv          # 割り当て済み VPC CIDR の一覧
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

**Actions → Run workflow** から **`create-project`**（外部リポジトリ管理の場合は **`create-project-external`**）を実行する。

| 入力 | 説明 |
|---|---|
| `project_name` | プロジェクト名（例: `my-project`） |
| `prod_email` | prod 用 AWS アカウントメールアドレス |
| `test_email` | test 用 AWS アカウントメールアドレス *（environments = `prod,test` のときのみ）* |
| `cidr_tier` | VPC CIDR 払い出し Tier: `C`（デフォルト・通常サービス）または `D`（マイクロサービス） |
| `environments` | `prod` または `prod,test` |
| `terraform_repo` | *（外部のみ）* 外部リポジトリ（例: `org/repo-name`） |

VPC CIDR は指定した Tier の次の空きスロットから自動で割り当てられる。割り当て結果は `.repo-meta/used_vpc_cidrs.csv` に記録される。

**Tier 一覧:**

| Tier | ブロック | VPC サイズ | 最大 VPC 数 | 用途 |
|---|---|---|---|---|
| A | `10.0.0.0/11` | `/16` | 32 | 共通インフラ |
| B | `10.32.0.0/11` | `/18` | 128 | 大規模サービス |
| C *（デフォルト）* | `10.64.0.0/10` | `/20` | 1,024 | 通常サービス |
| D | `10.128.0.0/10` | `/22` | 4,096 | マイクロサービス・IP消費が少ない場合 |
| *（予約済み）* | `10.192.0.0/10` | — | — | 将来の拡張用バッファ・割り当て対象外 |

手動での払い出しや現在の割り当て確認:

```bash
python scripts/allocate_cidr.py list
python scripts/allocate_cidr.py allocate --project <name> [--tier D]
```

PR **[1/3]** が作成される。各 PR をマージすると次の terraform apply が自動実行され、次の PR が作成される。3 つの PR を順番にマージするだけでよい:

| PR | 内容 | マージ時に自動 apply |
|---|---|---|
| `[1/3]` | プロジェクトのスキャフォールド | `platform-accounts` → account ID を取得 |
| `[2/3]` | `metadata.json` に `account_id` を記録 | `platform-bootstrap`、`platform-access`、`account-bootstrap` |
| `[3/3]` | `metadata.json` に `deploy_role_ready: true` を記録 | `platform-bootstrap`（S3 ポリシー最終更新） |

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
