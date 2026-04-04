# AWS multi-account Terraform monorepo

This repository is a **flat monorepo** designed for:

- **platform/**: management-account resources
- **projects/**: one directory per project account
- **.github/**: metadata-driven GitHub Actions workflows

The repository is intentionally designed so that **non-secret settings are stored in Git**:

- `backend.hcl` is committed
- `terraform.auto.tfvars` is committed
- `metadata.json` is committed
- secrets are **not** committed

This gives you:

- change history for bucket names, CIDR ranges, account emails, and target paths
- reproducible Terraform execution
- less local-only drift
- easier onboarding for additional projects

## Repository layout

```text
.
├── platform/
│   ├── metadata.json
│   ├── bootstrap/
│   ├── identity/
│   ├── accounts/
│   ├── access/
│   └── modules/
├── projects/
│   ├── _template/
│   └── project-a/
├── .github/
│   ├── workflows/
│   └── scripts/
├── .gitignore
└── README.md
```

## What is committed

Committed to Git:

- `backend.hcl`
- `terraform.auto.tfvars`
- `metadata.json`
- Terraform code

Not committed:

- `.terraform/`
- `terraform.tfstate`
- optional local secret files such as `secrets.auto.tfvars`

## Why this layout

### platform/
Use `platform/` for management-account resources:

- state bucket bootstrap
- GitHub OIDC provider
- GitHub Actions platform role
- AWS Organizations / OU / account creation
- IAM Identity Center permission sets and assignments

### projects/
Each project directory maps to one AWS account.

Each project contains:

- `metadata.json`
- `account-bootstrap/` for the project deploy role
- `envs/prod/` for project infrastructure
- `modules/` for project-local reusable modules

### metadata-driven workflows
The GitHub workflows read:

- `platform/metadata.json`
- `projects/<project>/metadata.json`

This removes the need to hardcode workflow logic for each project.

No per-project workflow edits are required when adding a new project.

---

## Prerequisites

You need:

- AWS Organizations enabled
- IAM Identity Center enabled
- Terraform CLI installed
- AWS CLI installed
- access to the management account
- one unused email address per AWS project account
- a GitHub repository for this monorepo

For the first setup, run Terraform locally first.

---

## Python environment setup with uv

This repository uses `pyproject.toml` and `uv.lock`.

### 1. Install uv

#### Windows

``` powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

#### macOS / Linux

``` bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Sync environment

Run from the repository root:

``` bash
uv sync
```

### 3. Run commands

``` bash
uv run python --version
```

---

## Setup order

Run Terraform in this order:

1. `platform/bootstrap`
2. `platform/identity`
3. `platform/accounts`
4. update each project `metadata.json` with the created account ID
5. `platform/access`
6. `projects/project-a/account-bootstrap`
7. `projects/project-a/envs/prod`

---

## Repo-managed configuration pattern

### 1. backend.hcl
`backend.hcl` is committed because it is not a secret.

Example:

```hcl
bucket       = "your-company-aws-tfstate-20260402"
key          = "projects/project-a/prod/terraform.tfstate"
region       = "ap-northeast-1"
use_lockfile = true
encrypt      = true
```

### 2. terraform.auto.tfvars
Each Terraform root contains a committed `terraform.auto.tfvars`.

Example:

```hcl
aws_region  = "ap-northeast-1"
name_prefix = "project-a-prod"
vpc_cidr    = "10.20.0.0/16"
```

### 3. metadata.json
Each project has committed metadata.

Example:

```json
{
  "project_name": "project-a",
  "display_name": "project-a",
  "account_email": "aws-project-a@example.com",
  "account_id": "123456789012",
  "region": "ap-northeast-1",
  "role_name": "GitHubActionsProjectDeployRole",
  "account_bootstrap_path": "projects/project-a/account-bootstrap",
  "prod_path": "projects/project-a/envs/prod",
  "enabled_for_access": true
}
```

---

## Platform metadata

`platform/metadata.json` is also committed and used by workflows to resolve the platform role ARN.

Example:

```json
{
  "management_account_id": "111111111111",
  "platform_role_name": "GitHubActionsPlatformRole",
  "region": "ap-northeast-1"
}
```

The workflow derives this ARN:

```text
arn:aws:iam::<management_account_id>:role/<platform_role_name>
```

---

## 1) platform/bootstrap

Creates the Terraform state bucket.

Edit:

- `platform/bootstrap/terraform.auto.tfvars`

Example:

```hcl
aws_region   = "ap-northeast-1"
state_bucket = "your-company-aws-tfstate-20260402"
```

Run:

```bash
cd platform/bootstrap
terraform init
terraform apply
```

---

## 2) platform/identity

Creates:

- GitHub OIDC provider in the management account
- GitHub Actions platform role in the management account

Files to edit:

- `platform/metadata.json`
- `platform/identity/backend.hcl`
- `platform/identity/terraform.auto.tfvars`

Example:

```hcl
aws_region  = "ap-northeast-1"
github_org  = "your-github-org"
github_repo = "your-repo-name"
role_name   = "GitHubActionsPlatformRole"
```

Run:

```bash
cd platform/identity
terraform init -backend-config=backend.hcl
terraform apply
```

---

## 3) platform/accounts

Discovers project metadata files automatically and creates AWS accounts for them.

No duplicate project map is required here.

Files to edit:

- `projects/<project>/metadata.json`
- `platform/accounts/backend.hcl`
- `platform/accounts/terraform.auto.tfvars`

Example project metadata before account creation:

```json
{
  "project_name": "project-b",
  "display_name": "project-b",
  "account_email": "aws-project-b@example.com",
  "account_id": "",
  "region": "ap-northeast-1",
  "role_name": "GitHubActionsProjectDeployRole",
  "account_bootstrap_path": "projects/project-b/account-bootstrap",
  "prod_path": "projects/project-b/envs/prod",
  "enabled_for_access": true
}
```

Run:

```bash
cd platform/accounts
terraform init -backend-config=backend.hcl
terraform apply
```

After apply, copy the created account ID from outputs back into `projects/<project>/metadata.json`.

---

## 4) platform/access

Discovers project metadata files and creates IAM Identity Center assignments for projects that:

- have `enabled_for_access = true`
- have a 12-digit `account_id`

Files to edit:

- `platform/access/backend.hcl`
- `platform/access/terraform.auto.tfvars`

Example:

```hcl
aws_region                   = "us-east-1"
identity_center_instance_arn = "arn:aws:sso:::instance/ssoins-xxxxxxxxxxxxxxxx"
principal_group_id           = "12345678-1234-1234-1234-123456789012"
permission_set_name          = "DeveloperAccess"
```

Run:

```bash
cd platform/access
terraform init -backend-config=backend.hcl
terraform apply
```

---

## 5) projects/<name>/account-bootstrap

Creates the GitHub Actions deploy role **inside the project account**.

Files to edit:

- `projects/<name>/account-bootstrap/backend.hcl`
- `projects/<name>/account-bootstrap/terraform.auto.tfvars`
- `projects/<name>/metadata.json`

Run this against the **project account**:

```bash
cd projects/project-a/account-bootstrap
terraform init -backend-config=backend.hcl
terraform apply
```

The workflow later derives the role ARN from:

- `account_id`
- `role_name`

stored in `metadata.json`

So you do not need to define `AWS_ROLE_ARN_PROJECT_A` in GitHub variables.

---

## 6) projects/<name>/envs/prod

Deploy project infrastructure.

Files to edit:

- `projects/<name>/envs/prod/backend.hcl`
- `projects/<name>/envs/prod/terraform.auto.tfvars`

Run against the **project account**:

```bash
cd projects/project-a/envs/prod
terraform init -backend-config=backend.hcl
terraform apply
```

---

## GitHub Actions behavior

### Pull requests
- discover targets from metadata
- detect changed directories
- run `terraform plan` only for changed targets

### Manual apply
- choose a target path
- resolve the correct AWS role ARN from metadata
- run `terraform apply`

### Template protection
`projects/_template` is always rejected for apply.

---

## How role ARN resolution works

The workflows do not read project role ARNs from GitHub variables.

Instead they derive them like this:

### Platform
From `platform/metadata.json`:

```text
arn:aws:iam::<management_account_id>:role/<platform_role_name>
```

### Project
From `projects/<name>/metadata.json`:

```text
arn:aws:iam::<account_id>:role/<role_name>
```

This means the repo remains the source of truth.

---

## How to add a new project

Example: add `project-b`

### Step 1
Scaffold it from the template:

```bash
uv run .github/scripts/new_project.py project-b aws-project-b@example.com 10.21.0.0/16
```

This creates:

- `projects/project-b/metadata.json`
- `projects/project-b/account-bootstrap/*`
- `projects/project-b/envs/prod/*`
- `projects/project-b/modules/*`

### Step 2
Review and edit:

- `projects/project-b/metadata.json`
- `projects/project-b/account-bootstrap/terraform.auto.tfvars`
- `projects/project-b/envs/prod/terraform.auto.tfvars`

### Step 3
Create the AWS account:

```bash
cd platform/accounts
terraform apply
```

### Step 4
Copy the created account ID into `projects/project-b/metadata.json`

### Step 5
Grant IAM Identity Center access:

```bash
cd platform/access
terraform apply
```

### Step 6
Create the project deploy role in the project account:

```bash
cd projects/project-b/account-bootstrap
terraform apply
```

### Step 7
Deploy project infrastructure:

```bash
cd projects/project-b/envs/prod
terraform apply
```

No workflow file changes are needed.

---

## Cost notes

This repository stays intentionally low-cost:

- no NAT Gateway by default
- no ALB by default
- only a VPC skeleton in the example project
- no always-on compute in the template

Watch costs for:

- NAT Gateway
- Public IPv4
- ALB / NLB
- EC2 / RDS
- CloudWatch Logs retention

---

## Recommended operating rules

- keep one Terraform state per root module
- never deploy `projects/_template`
- keep CIDR ranges unique across projects
- run project Terraform against the correct AWS account
- commit non-secret config, keep secrets out of Git

---

## Handy checklist

```text
[ ] Edit platform/metadata.json
[ ] Apply platform/bootstrap
[ ] Apply platform/identity
[ ] Add or scaffold a project
[ ] Apply platform/accounts
[ ] Update projects/<name>/metadata.json with account_id
[ ] Apply platform/access
[ ] Apply projects/<name>/account-bootstrap
[ ] Apply projects/<name>/envs/prod
[ ] Create PR and verify plan
```
