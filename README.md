# Projects Infra

This repository is AWS multi-account Terraform monorepo.

## 🚀 Quick Start (Recommended)

Create a new project with a single command:

```bash
py .github/scripts/create_project.py project-b aws-project-b@example.com 10.21.0.0/16
```

This will automatically:

- Create project scaffold
- Validate CIDR (no overlap)
- Create AWS account
- Update metadata.json
- Configure S3 state access
- Configure IAM Identity Center access
- Assume OrganizationAccountAccessRole
- Create deploy role
- Enable GitHub Actions
- Optionally deploy infrastructure

You only need to approve Terraform apply steps.

---

## 📁 Repository Layout

```
platform/   # management account resources
projects/   # per-project AWS accounts
.github/    # workflows and scripts
```

---

## 🔐 S3 State Model

- Centralized state bucket (management account)
- Prefix-based access:

```
projects/<project-name>/*
```

- Automatically managed via metadata.json
- No manual bucket policy edits required

---

## 🧠 Execution Model

- Uses OrganizationAccountAccessRole via assume-role
- No need for per-project AWS profiles
- Fully automated by script

---

## ⚙️ Initial Setup (One-time)

```bash
cd platform/bootstrap
terraform apply

cd platform/identity
terraform apply
```

---

## ➕ Add Project

```bash
py .github/scripts/create_project.py project-b aws-project-b@example.com 10.21.0.0/16
```

---

## 🔧 Manual Flow (Advanced)

1. new_project.py
2. platform/accounts
3. update metadata.json
4. platform/bootstrap
5. platform/access
6. account-bootstrap
7. set deploy_role_ready=true
8. platform/bootstrap
9. envs/prod

---

## 💰 Cost Notes

- No NAT Gateway by default
- Minimal infra footprint
- Watch:
  - NAT Gateway
  - Public IP
  - ALB/NLB
  - EC2/RDS

---

## ✅ Checklist

```
[ ] platform/bootstrap applied
[ ] platform/identity applied
[ ] project created
[ ] infrastructure deployed
```
