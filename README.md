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
    terraform-plan.yml           # Auto-detect changed targets and plan on PR
    terraform-apply.yml          # Manual dispatch to apply
    create-project.yml           # Scaffold new project and open PR (this repo)
    create-project-external.yml  # Scaffold new project and open PR (external repo)
  scripts/
    new_project.py            # Scaffold project directory from template
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

Trigger **`create-project`** (or **`create-project-external`** for external repo) from **Actions → Run workflow** with:

| Input | Description |
|---|---|
| `project_name` | Project name (e.g. `my-project`) |
| `account_email` | Base AWS account email |
| `vpc_cidr` | VPC CIDR block (e.g. `10.1.0.0/16`) |
| `environments` | `prod` or `prod,test` |
| `terraform_repo` | *(external only)* External repo (e.g. `org/repo-name`) |

This opens PR **[1/3]**. Merging each PR automatically triggers the next terraform applies and creates the following PR. Just merge the three PRs in order:

| PR | Content | Auto-applies on merge |
|---|---|---|
| `[1/3]` | Project scaffold | `platform-accounts` → captures account IDs |
| `[2/3]` | `account_id` set in `metadata.json` | `platform-bootstrap`, `platform-access`, `account-bootstrap` |
| `[3/3]` | `deploy_role_ready: true` in `metadata.json` | `platform-bootstrap` (final S3 policy update) |

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
