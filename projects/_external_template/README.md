# External Terraform Template

Template for projects managed in projects-infra where Terraform code lives in an external repository.

## Setup

### 1. Copy this directory's contents into the external repository

```
.github/workflows/terraform-plan.yml
.github/workflows/terraform-apply.yml
backend.hcl
```

### 2. Set GitHub repository variables

Go to **Settings → Secrets and variables → Actions → Variables** in the external repository and add:

| Variable | Value |
|---|---|
| `PROJECT_NAME` | Project name as registered in projects-infra (e.g. `my-project`). Used as the S3 state key prefix: `projects/<PROJECT_NAME>/<env>/terraform.tfstate` |
| `PROD_ACCOUNT_ID` | AWS account ID for the prod environment |
| `TEST_ACCOUNT_ID` | AWS account ID for the test environment |

The S3 bucket name is shared and fixed — no changes needed in `backend.hcl`.

For prod-only projects, remove the `test` entry from the matrix in `terraform-plan.yml` and the `test` case in `terraform-apply.yml`.

### 3. Place Terraform code

By default, `.tf` files are expected at the repository root:

```
your-repo/
  main.tf
  variables.tf
  backend.hcl   ← place here
  .github/workflows/
```

To use a subdirectory (e.g. `terraform/`), update the env variable at the top of both workflow files:

```yaml
env:
  TF_WORKING_DIR: "terraform"   # ← change from "."
```

In this case, place `backend.hcl` inside the same subdirectory.

### 4. Declare `variable "environment"`

The environment is injected via `TF_VAR_environment`, so declare it in your Terraform code:

```hcl
variable "environment" {
  type = string
}
```

### 5. Verify prerequisites in projects-infra

For the external repository to assume `GitHubActionsProjectDeployRole`, the following must be set up in projects-infra:

- `additional_github_repos = ["org/this-repo"]` added to `projects/<name>/account-bootstrap/terraform.auto.tfvars`
- account-bootstrap has been applied and `deploy_role_ready = true`

## S3 State Keys

State is stored in the shared S3 bucket alongside projects-infra under the following keys:

```
projects/<PROJECT_NAME>/prod/terraform.tfstate
projects/<PROJECT_NAME>/test/terraform.tfstate
```

## Workflow Behavior

| Workflow | Trigger | Description |
|---|---|---|
| `terraform-plan` | PR created / updated | Runs plan for prod and test in parallel |
| `terraform-apply` | Manual (workflow_dispatch) | Select an environment and apply |
