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

workloads/                    # Per-workload AWS accounts
  _template/                  # Template for new workloads (never applied)
  _external_template/         # Template for externally managed workloads
  <workload-name>/
    account-bootstrap/        # OIDC provider and deploy role setup
    envs/                     # Infrastructure resources; environment injected via var.environment
    modules/                  # Workload-specific modules
    metadata.json             # Workload configuration

.github/
  workflows/
    terraform-plan.yml           # Auto-detect changed targets and plan on PR
    terraform-apply.yml          # Manual dispatch to apply
    create-workload.yml          # Scaffold new workload and open PR (this repo)
    create-workload-external.yml # Scaffold new workload and open PR (external repo)
  scripts/
    new_workload.py          # Scaffold workload directory from template
    discover_targets.py      # Terraform target discovery
    filter_changed_targets.py # Filter targets by git diff
    resolve_role_arn.py      # Resolve IAM role for each target

scripts/
  allocate_cidr.py            # VPC CIDR allocation tool (tier-based sequential assignment)

.repo-meta/
  used_vpc_cidrs.csv          # Registry of all allocated VPC CIDRs
```

---

## ⚙️ GitHub Actions

### Plan (on PR)

Opening a PR with changes under `platform/**` or `workloads/**` automatically runs `terraform plan` for each changed target.

### Apply (manual)

Trigger `terraform-apply.yml` via workflow dispatch, specifying the `target_name` (e.g. `workloads/project-a/envs:prod` or `workloads/project-a/bootstrap:prod`).

### Authentication (OIDC)

No static AWS credentials are stored. GitHub OIDC is used to assume the appropriate role per target.

| Target kind | Role assumed |
|---|---|
| `platform`, `platform-bootstrap` | `GitHubActionsPlatformRole` (management account) |
| `workload-bootstrap` (deploy_role_ready=false) | ① `GitHubActionsPlatformRole` → ② chain to `OrganizationAccountAccessRole` (workload account) |
| `workload-bootstrap` (deploy_role_ready=true) | `GitHubActionsWorkloadDeployRole` (workload account) |
| `workload` | `GitHubActionsWorkloadDeployRole` (workload account) |

---

## 🗂 Two Terraform Management Modes

### Managed in this repo (default)

Place `envs/` in this repo and let GitHub Actions handle plan/apply. The `environment` variable is injected at CI time via `TF_VAR_environment`.

### Managed in an external repo

Set `terraform_repo` in `metadata.json` to opt a workload out of this repo's GitHub Actions. The external repo manages `envs/` independently.

```json
{
  "terraform_repo": "org/external-repo-name"
}
```

See `workloads/_external_template/` for the workflow and backend configuration to place in the external repo.

To make the account-bootstrap OIDC role trust the external repo, add the following to `terraform.auto.tfvars` and re-apply `account-bootstrap`:

```hcl
additional_github_repos = ["org/external-repo-name"]
```

---

## ➕ Adding a Workload

Trigger **`create-workload`** (or **`create-workload-external`** for external repo) from **Actions → Run workflow** with:

| Input | Description |
|---|---|
| `workload_name` | Workload name (e.g. `my-service`) |
| `prod_email` | AWS account email for prod |
| `test_email` | AWS account email for test *(only when environments = `prod,test`)* |
| `cidr_tier` | Tier for VPC CIDR allocation: `C` (default, normal service) or `D` (microservice) |
| `environments` | `prod` or `prod,test` |
| `terraform_repo` | *(external only)* External repo (e.g. `org/repo-name`) |

The VPC CIDR is automatically assigned from the next available slot in the chosen tier. All allocations are recorded in `.repo-meta/used_vpc_cidrs.csv`.

**Tier reference:**

| Tier | Block | VPC size | Max VPCs | Use when |
|---|---|---|---|---|
| A | `10.0.0.0/11` | `/16` | 32 | Common infrastructure (not normally used) |
| B | `10.32.0.0/11` | `/18` | 128 | Large-scale services (not normally used) |
| C *(default)* | `10.64.0.0/10` | `/20` | 1,024 | Normal service |
| D | `10.128.0.0/10` | `/22` | 4,096 | Microservice / low IP consumption |
| *(reserved)* | `10.192.0.0/10` | — | — | Buffer for future use; not allocated |

To allocate a CIDR manually or check current assignments:

```bash
python scripts/allocate_cidr.py list
python scripts/allocate_cidr.py allocate --workload <name> [--tier D]
```

This opens PR **[1/3]**. Merging each PR automatically triggers the next terraform applies and creates the following PR. Just merge the three PRs in order:

| PR | Content | Auto-applies on merge |
|---|---|---|
| `[1/3]` | Workload scaffold | `platform-accounts` → captures account IDs |
| `[2/3]` | `account_id` set in `metadata.json` | `platform-bootstrap`, `platform-access`, `account-bootstrap` |
| `[3/3]` | `deploy_role_ready: true` in `metadata.json` | `platform-bootstrap` (final S3 policy update) |

---

## 🗃 S3 State

- All state is stored in a single S3 bucket in the management account
- Per-environment isolation via key prefix: `workloads/<workload-name>/<env>/*`
- Bucket policies are managed automatically from `metadata.json`

---

## ⚙️ Initial Setup (one-time)

```bash
cd platform/bootstrap && terraform apply
cd platform/identity  && terraform apply
cd platform/accounts  && terraform apply
cd platform/access    && terraform apply
```
