
#!/usr/bin/env python3
"""
Windows-friendly project bootstrap helper for the Terraform monorepo.

What it does:
1. Calls the existing .github/scripts/new_project.py
2. For each environment:
   a. Runs platform/accounts terraform apply
   b. Reads the created account_id from terraform output
   c. Updates projects/<name>/metadata.json
   d. Runs platform/bootstrap terraform apply
   e. Runs platform/access terraform apply
   f. Assumes OrganizationAccountAccessRole in the project account
   g. Runs projects/<name>/account-bootstrap terraform apply
   h. Marks deploy_role_ready=true in metadata.json
   i. Runs platform/bootstrap terraform apply again
3. Optionally runs projects/<name>/envs terraform apply for each environment

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


def terraform_init_and_apply(
    root: Path,
    env: dict[str, str],
    backend: bool = True,
    backend_key: str | None = None,
    tf_vars: dict[str, str] | None = None,
) -> None:
    if backend:
        init_cmd = ["terraform", "init", "-reconfigure", "-backend-config=backend.hcl"]
        if backend_key:
            init_cmd.append(f"-backend-config=key={backend_key}")
        run(init_cmd, cwd=root, env=env)
    else:
        run(["terraform", "init", "-reconfigure", "-backend=false"], cwd=root, env=env)

    plan_cmd = ["terraform", "plan"]
    if tf_vars:
        for k, v in tf_vars.items():
            plan_cmd += ["-var", f"{k}={v}"]
    run(plan_cmd, cwd=root, env=env)

    if not ask_yes_no(f"Apply Terraform in {root}?", default=False):
        fail(f"Aborted by user before apply: {root}", 2)

    apply_cmd = ["terraform", "apply"]
    if tf_vars:
        for k, v in tf_vars.items():
            apply_cmd += ["-var", f"{k}={v}"]
    run(apply_cmd, cwd=root, env=env)


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


def update_project_metadata_account_id(
    repo: Path, project_name: str, env_name: str, account_id: str
) -> Path:
    metadata_path = repo / "projects" / project_name / "metadata.json"
    metadata = load_json(metadata_path)
    metadata["environments"][env_name]["account_id"] = account_id
    metadata["environments"][env_name].setdefault("deploy_role_ready", False)
    save_json(metadata_path, metadata)
    info(f"Updated account_id for {env_name} in {metadata_path}")
    return metadata_path


def mark_deploy_role_ready(
    repo: Path, project_name: str, env_name: str, ready: bool = True
) -> None:
    metadata_path = repo / "projects" / project_name / "metadata.json"
    metadata = load_json(metadata_path)
    metadata["environments"][env_name]["deploy_role_ready"] = ready
    save_json(metadata_path, metadata)
    info(f"Updated deploy_role_ready={ready} for {env_name} in {metadata_path}")


def create_project_scaffold(
    repo: Path, project_name: str, account_email: str, vpc_cidr: str, environments: list[str]
) -> None:
    script = repo / ".github" / "scripts" / "new_project.py"
    envs_arg = ",".join(environments)
    run([sys.executable, str(script), project_name, account_email, vpc_cidr, envs_arg], cwd=repo)


def bootstrap_environment(
    repo: Path,
    project_name: str,
    env_name: str,
    mgmt_env: dict[str, str],
    management_profile: str,
    default_region: str,
    platform_bootstrap: Path,
    platform_accounts: Path,
    platform_access: Path,
) -> None:
    info(f"=== Bootstrapping environment: {env_name} ===")

    info(f"[{env_name}] platform/accounts apply")
    terraform_init_and_apply(platform_accounts, mgmt_env, backend=True)

    outputs = terraform_output_json(platform_accounts, mgmt_env)
    env_key = f"{project_name}-{env_name}"
    try:
        account_id = outputs["project_account_ids"]["value"][env_key]
    except KeyError as exc:
        fail(f"Could not find account ID for {env_key} in platform/accounts output: {exc}")

    info(f"[{env_name}] AWS account ID: {account_id}")
    update_project_metadata_account_id(repo, project_name, env_name, account_id)

    info(f"[{env_name}] platform/bootstrap apply")
    terraform_init_and_apply(platform_bootstrap, mgmt_env, backend=True)

    info(f"[{env_name}] platform/access apply")
    terraform_init_and_apply(platform_access, mgmt_env, backend=True)

    info(f"[{env_name}] Assume OrganizationAccountAccessRole")
    project_env = assume_org_access_role(
        management_profile=management_profile,
        account_id=account_id,
        role_name="OrganizationAccountAccessRole",
        region=default_region,
    )

    bootstrap_key = f"projects/{project_name}/{env_name}/account-bootstrap/terraform.tfstate"
    project_account_bootstrap = repo / "projects" / project_name / "account-bootstrap"
    info(f"[{env_name}] account-bootstrap apply")
    terraform_init_and_apply(
        project_account_bootstrap,
        project_env,
        backend=True,
        backend_key=bootstrap_key,
    )

    mark_deploy_role_ready(repo, project_name, env_name, True)

    info(f"[{env_name}] platform/bootstrap apply (add deploy role to S3 policy)")
    terraform_init_and_apply(platform_bootstrap, mgmt_env, backend=True)


def main() -> None:
    if len(sys.argv) < 4:
        fail("usage: create_project.py <project-name> <account-email> <vpc-cidr> [environments]", 2)

    project_name  = sys.argv[1].strip()
    account_email = sys.argv[2].strip()
    vpc_cidr      = sys.argv[3].strip()
    environments  = [e.strip() for e in sys.argv[4].split(",")] if len(sys.argv) > 4 else ["prod"]

    if not project_name or not account_email or not vpc_cidr:
        fail("project-name, account-email, and vpc-cidr are required")

    repo = repo_root_from_script()

    management_profile = os.environ.get("MANAGEMENT_AWS_PROFILE", "management-admin")
    default_region = os.environ.get("AWS_REGION", "ap-northeast-1")

    platform_bootstrap = repo / "platform" / "bootstrap"
    platform_accounts  = repo / "platform" / "accounts"
    platform_access    = repo / "platform" / "access"
    project_envs       = repo / "projects" / project_name / "envs"

    info("Step 0: Login to management account")
    ensure_management_login(management_profile)
    mgmt_env = build_env_with_profile(management_profile)

    info("Step 1: Create project scaffold from template")
    create_project_scaffold(repo, project_name, account_email, vpc_cidr, environments)

    for env_name in environments:
        bootstrap_environment(
            repo=repo,
            project_name=project_name,
            env_name=env_name,
            mgmt_env=mgmt_env,
            management_profile=management_profile,
            default_region=default_region,
            platform_bootstrap=platform_bootstrap,
            platform_accounts=platform_accounts,
            platform_access=platform_access,
        )

    for env_name in environments:
        envs_key = f"projects/{project_name}/{env_name}/terraform.tfstate"
        if ask_yes_no(f"Also apply projects/{project_name}/envs for {env_name}?", default=True):
            metadata = load_json(repo / "projects" / project_name / "metadata.json")
            env_cfg = metadata["environments"][env_name]
            project_env = assume_org_access_role(
                management_profile=management_profile,
                account_id=env_cfg["account_id"],
                region=default_region,
            )
            info(f"[{env_name}] projects/{project_name}/envs apply")
            terraform_init_and_apply(
                project_envs,
                project_env,
                backend=True,
                backend_key=envs_key,
                tf_vars={"environment": env_name},
            )
        else:
            warn(f"Skipped envs apply for {env_name}.")

    info("Done.")
    print("")
    print("Next recommended checks:")
    print(f"  1. Confirm metadata: projects/{project_name}/metadata.json")
    print(f"  2. Confirm bucket policy prefix access via platform/bootstrap")
    for env_name in environments:
        print(f"  3. Test GitHub Actions plan for {project_name}-{env_name}")


if __name__ == "__main__":
    main()
