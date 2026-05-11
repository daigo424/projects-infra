# Projects Infra

AWS multi-account Terraform monorepo.

## 📁 Repository Layout

```
platform/                     # Management account resources
  bootstrap/                  # S3 state bucket and access policies
  accounts/                   # AWS Organizations account creation
  identity/                   # GitHub OIDC provider (management account)
  access/                     # IAM Identity Center configuration
  modules/github_oidc_role/   # Reusable OIDC role module
  metadata.json               # Management account configuration

projects/                     # Per-project AWS accounts
  _template/                  # Template for new projects (never applied)
  _external_template/         # Template for externally managed projects
  <project-name>/
    account-bootstrap/        # OIDC provider and deploy role setup
    envs/                     # Infrastructure resources; environment injected via var.environment
    modules/                  # Project-specific modules
    metadata.json             # Project configuration

.github/
  workflows/
    terraform-plan.yml        # Auto-detect changed targets and plan on PR
    terraform-apply.yml       # Manual dispatch to apply
  scripts/
    create_project.py         # Project creation script
    discover_targets.py       # Terraform target discovery
    filter_changed_targets.py # Filter targets by git diff
    resolve_role_arn.py       # Resolve IAM role for each target
```

---

## ⚙️ GitHub Actions

### Plan (on PR)

Opening a PR with changes under `platform/**` or `projects/**` automatically runs `terraform plan` for each changed target.

### Apply (manual)

Trigger `terraform-apply.yml` via workflow dispatch, specifying the `target_name` (e.g. `project-a-prod` or `project-a-test-account-bootstrap`).

### Authentication (OIDC)

No static AWS credentials are stored. GitHub OIDC is used to assume the appropriate role per target.

| Target kind | Role assumed |
|---|---|
| `platform`, `platform-bootstrap` | `GitHubActionsPlatformRole` (management account) |
| `project-bootstrap` (deploy_role_ready=false) | ① `GitHubActionsPlatformRole` → ② chain to `OrganizationAccountAccessRole` (project account) |
| `project-bootstrap` (deploy_role_ready=true) | `GitHubActionsProjectDeployRole` (project account) |
| `project` | `GitHubActionsProjectDeployRole` (project account) |

---

## 🗂 Two Terraform Management Modes

### Managed in this repo (default)

Place `envs/` in this repo and let GitHub Actions handle plan/apply. The `environment` variable is injected at CI time via `TF_VAR_environment`.

### Managed in an external repo

Set `terraform_repo` in `metadata.json` to opt a project out of this repo's GitHub Actions. The external repo manages `envs/` independently.

```json
{
  "terraform_repo": "org/external-repo-name"
}
```

See `projects/_external_template/` for the workflow and backend configuration to place in the external repo.

To make the account-bootstrap OIDC role trust the external repo, add the following to `terraform.auto.tfvars` and re-apply `account-bootstrap`:

```hcl
additional_github_repos = ["org/external-repo-name"]
```

---

## ➕ Adding a Project

```bash
py .github/scripts/create_project.py <project-name> <email> <vpc-cidr> [environments]
# Example (prod only):    py .github/scripts/create_project.py my-project me@example.com 10.0.0.0/16
# Example (prod + test):  py .github/scripts/create_project.py my-project me@example.com 10.0.0.0/16 prod,test
```

The following steps are performed for each environment:

1. Scaffold project directory from `_template`
2. Apply `platform/accounts` — create AWS account (`PROD-<project>` or `TEST-<project>`)
3. Record `account_id` in `metadata.json`
4. Apply `platform/bootstrap` — update S3 access policy
5. Apply `platform/access` — configure IAM Identity Center
6. Apply `account-bootstrap` — create OIDC provider and deploy role (via GitHub Actions role-chaining to `OrganizationAccountAccessRole`)
7. Set `deploy_role_ready=true` in `metadata.json`
8. Apply `platform/bootstrap` — add S3 policy for deploy role
9. (Optional) Apply `envs` with `TF_VAR_environment=<env>` — deploy infrastructure

---

## 🗃 S3 State

- All state is stored in a single S3 bucket in the management account
- Per-environment isolation via key prefix: `projects/<project-name>/<env>/*`
- Bucket policies are managed automatically from `metadata.json`

---

## ⚙️ Initial Setup (one-time)

```bash
cd platform/bootstrap && terraform apply
cd platform/identity  && terraform apply
cd platform/accounts  && terraform apply
cd platform/access    && terraform apply
```
