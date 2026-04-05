
#!/usr/bin/env python3
"""
Windows-friendly project bootstrap helper for the Terraform monorepo.

What it does:
1. Calls the existing .github/scripts/new_project.py
2. Runs platform/accounts terraform apply
3. Reads the created account_id from terraform output
4. Updates projects/<name>/metadata.json
5. Runs platform/bootstrap terraform apply
6. Runs platform/access terraform apply
7. Assumes OrganizationAccountAccessRole in the new project account
8. Runs projects/<name>/account-bootstrap terraform apply
9. Marks deploy_role_ready=true in metadata.json
10. Runs platform/bootstrap terraform apply again
11. Optionally runs projects/<name>/envs/prod terraform apply

Notes:
- This script expects platform/bootstrap, platform/accounts, platform/access
  to be runnable with the management profile.
- It prompts before each terraform apply.
- It does not require a pre-created "project-x-bootstrap" AWS profile.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def warn(msg: str) -> None:
    print(f"[WARN] {msg}")


def fail(msg: str, code: int = 1) -> None:
    print(f"[ERROR] {msg}", file=sys.stderr)
    raise SystemExit(code)


def ask_yes_no(question: str, default: bool = False) -> bool:
    prompt = " [Y/n]: " if default else " [y/N]: "
    answer = input(question + prompt).strip().lower()
    if not answer:
        return default
    return answer in {"y", "yes"}


def run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    info(f"Running: {' '.join(cmd)}")
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def terraform_init_and_apply(root: Path, env: dict[str, str], backend: bool = True) -> None:
    if backend:
        run(["terraform", "init", "-reconfigure", "-backend-config=backend.hcl"], cwd=root, env=env)
    else:
        run(["terraform", "init", "-reconfigure", "-backend=false"], cwd=root, env=env)

    run(["terraform", "plan"], cwd=root, env=env)

    if not ask_yes_no(f"Apply Terraform in {root}?", default=False):
        fail(f"Aborted by user before apply: {root}", 2)

    run(["terraform", "apply"], cwd=root, env=env)


def terraform_output_json(root: Path, env: dict[str, str]) -> dict[str, Any]:
    cp = run(["terraform", "output", "-json"], cwd=root, env=env, capture_output=True)
    return json.loads(cp.stdout)


def build_env_with_profile(profile: str) -> dict[str, str]:
    env = os.environ.copy()
    env["AWS_PROFILE"] = profile
    env.pop("AWS_ACCESS_KEY_ID", None)
    env.pop("AWS_SECRET_ACCESS_KEY", None)
    env.pop("AWS_SESSION_TOKEN", None)
    return env


def assume_org_access_role(
    management_profile: str,
    account_id: str,
    role_name: str = "OrganizationAccountAccessRole",
    region: str = "ap-northeast-1",
) -> dict[str, str]:
    info(f"Assuming {role_name} in account {account_id}")
    cp = run(
        [
            "aws",
            "sts",
            "assume-role",
            "--profile",
            management_profile,
            "--role-arn",
            f"arn:aws:iam::{account_id}:role/{role_name}",
            "--role-session-name",
            f"bootstrap-{account_id}",
        ],
        capture_output=True,
    )
    payload = json.loads(cp.stdout)
    creds = payload["Credentials"]

    env = os.environ.copy()
    env.pop("AWS_PROFILE", None)
    env["AWS_ACCESS_KEY_ID"] = creds["AccessKeyId"]
    env["AWS_SECRET_ACCESS_KEY"] = creds["SecretAccessKey"]
    env["AWS_SESSION_TOKEN"] = creds["SessionToken"]
    env["AWS_DEFAULT_REGION"] = region
    env["AWS_REGION"] = region
    return env


def ensure_management_login(profile: str) -> None:
    if ask_yes_no(f"Run 'aws sso login --profile {profile}' now?", default=True):
        run(["aws", "sso", "login", "--profile", profile])


def update_project_metadata_account_id(repo: Path, project_name: str, account_id: str) -> Path:
    metadata_path = repo / "projects" / project_name / "metadata.json"
    metadata = load_json(metadata_path)
    metadata["account_id"] = account_id
    metadata.setdefault("role_name", "GitHubActionsProjectDeployRole")
    metadata.setdefault("deploy_role_ready", False)
    save_json(metadata_path, metadata)
    info(f"Updated account_id in {metadata_path}")
    return metadata_path


def mark_deploy_role_ready(repo: Path, project_name: str, ready: bool = True) -> None:
    metadata_path = repo / "projects" / project_name / "metadata.json"
    metadata = load_json(metadata_path)
    metadata["deploy_role_ready"] = ready
    save_json(metadata_path, metadata)
    info(f"Updated deploy_role_ready={ready} in {metadata_path}")


def create_project_scaffold(repo: Path, project_name: str, account_email: str, vpc_cidr: str) -> None:
    script = repo / ".github" / "scripts" / "new_project.py"
    run([sys.executable, str(script), project_name, account_email, vpc_cidr], cwd=repo)


def main() -> None:
    if len(sys.argv) != 4:
        fail("usage: create_project.py <project-name> <account-email> <vpc-cidr>", 2)

    project_name = sys.argv[1].strip()
    account_email = sys.argv[2].strip()
    vpc_cidr = sys.argv[3].strip()

    if not project_name or not account_email or not vpc_cidr:
        fail("project-name, account-email, and vpc-cidr are required")

    repo = repo_root_from_script()

    management_profile = os.environ.get("MANAGEMENT_AWS_PROFILE", "management-admin")
    default_region = os.environ.get("AWS_REGION", "ap-northeast-1")

    platform_bootstrap = repo / "platform" / "bootstrap"
    platform_accounts = repo / "platform" / "accounts"
    platform_access = repo / "platform" / "access"
    project_account_bootstrap = repo / "projects" / project_name / "account-bootstrap"
    project_prod = repo / "projects" / project_name / "envs" / "prod"

    info("Step 0: Login to management account")
    ensure_management_login(management_profile)
    mgmt_env = build_env_with_profile(management_profile)

    info("Step 1: Create project scaffold from template")
    create_project_scaffold(repo, project_name, account_email, vpc_cidr)

    info("Step 2: platform/accounts")
    terraform_init_and_apply(platform_accounts, mgmt_env, backend=True)

    outputs = terraform_output_json(platform_accounts, mgmt_env)
    try:
        account_id = outputs["project_account_ids"]["value"][project_name]
    except KeyError as exc:
        fail(f"Could not find account ID for {project_name} in platform/accounts output: {exc}")

    info(f"Created/Found AWS account ID for {project_name}: {account_id}")

    info("Step 3: Update metadata.json with account_id")
    update_project_metadata_account_id(repo, project_name, account_id)

    info("Step 4: platform/bootstrap (grant S3 state access for this project)")
    terraform_init_and_apply(platform_bootstrap, mgmt_env, backend=True)

    info("Step 5: platform/access (grant IAM Identity Center access if configured)")
    terraform_init_and_apply(platform_access, mgmt_env, backend=True)

    info("Step 6: Assume OrganizationAccountAccessRole into the project account")
    project_env = assume_org_access_role(
        management_profile=management_profile,
        account_id=account_id,
        role_name="OrganizationAccountAccessRole",
        region=default_region,
    )

    info("Step 7: projects/<name>/account-bootstrap")
    terraform_init_and_apply(project_account_bootstrap, project_env, backend=True)

    info("Step 8: Mark deploy_role_ready=true")
    mark_deploy_role_ready(repo, project_name, True)

    info("Step 9: platform/bootstrap again (now include project deploy role in S3 bucket policy)")
    terraform_init_and_apply(platform_bootstrap, mgmt_env, backend=True)

    if ask_yes_no(f"Also run terraform for {project_prod} now?", default=True):
        info("Step 10: projects/<name>/envs/prod")
        terraform_init_and_apply(project_prod, project_env, backend=True)
    else:
        warn("Skipped project prod apply by user request.")

    info("Done.")
    print("")
    print("Next recommended checks:")
    print(f"  1. Confirm metadata: projects/{project_name}/metadata.json")
    print(f"  2. Confirm bucket policy prefix access via platform/bootstrap")
    print(f"  3. Test GitHub Actions plan for projects/{project_name}/envs/prod")


if __name__ == "__main__":
    main()
