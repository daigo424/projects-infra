#!/usr/bin/env python3
import json
import shutil
import sys
from pathlib import Path
from typing import NoReturn

from filelock import FileLock


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def fail(message: str, exit_code: int = 1) -> NoReturn:
    eprint(message)
    raise SystemExit(exit_code)


def parse_args() -> tuple[str, list[str], str, dict[str, str], str]:
    if len(sys.argv) < 5:
        fail(
            "usage: new_workload.py <workload-name> <environments> <cidr-tier> <prod-email>"
            " [<test-email>] [<member-email>]",
            exit_code=2,
        )

    workload_name = sys.argv[1].strip()
    environments  = [e.strip() for e in sys.argv[2].split(",")]
    cidr_tier     = sys.argv[3].strip().upper()
    prod_email    = sys.argv[4].strip()
    test_email    = sys.argv[5].strip() if len(sys.argv) > 5 else ""
    member_email  = sys.argv[6].strip() if len(sys.argv) > 6 else ""

    if not workload_name:
        fail("workload-name must not be empty")

    valid_tiers = {"A", "B", "C", "D"}
    if cidr_tier not in valid_tiers:
        fail(f"unknown tier '{cidr_tier}'. Must be one of: {', '.join(sorted(valid_tiers))}")

    valid_envs = {"prod", "test"}
    for env in environments:
        if env not in valid_envs:
            fail(f"unknown environment '{env}'. Must be one of: {', '.join(sorted(valid_envs))}")

    env_emails: dict[str, str] = {"prod": prod_email}
    if "test" in environments:
        if not test_email:
            fail("test-email is required when environments includes 'test'")
        env_emails["test"] = test_email

    for env, email in env_emails.items():
        if not email:
            fail(f"email for '{env}' must not be empty")
        if "@" not in email:
            fail(f"invalid email for '{env}': {email}")
        if len(email) > 64:
            fail(
                f"Email for '{env}' too long ({len(email)} chars, max 64 for AWS Organizations):\n"
                f"  {email}"
            )

    return workload_name, environments, cidr_tier, env_emails, member_email


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def replace_placeholders_in_text_files(target_dir: Path, workload_name: str, prod_email: str) -> None:
    replacements = {
        "__WORKLOAD_NAME__": workload_name,
    }
    for path in target_dir.rglob("*"):
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for before, after in replacements.items():
            content = content.replace(before, after)
        path.write_text(content, encoding="utf-8")


def update_metadata(
    target_dir: Path,
    workload_name: str,
    environments: list[str],
    cidr_tier: str,
    vpc_cidr: str,
    env_emails: dict[str, str],
    member_email: str,
) -> None:
    metadata_path = target_dir / "metadata.json"
    if not metadata_path.exists():
        fail(f"metadata.json not found: {metadata_path}")

    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid metadata.json: {metadata_path}: {exc}")

    env_map = {}
    for env_name in environments:
        env_map[env_name] = {
            "account_id": "",
            "account_email": env_emails[env_name],
            "enabled_for_access": True,
            "deploy_role_ready": False,
        }

    metadata["workload_name"] = workload_name
    metadata["display_name"] = workload_name
    metadata["account_bootstrap_path"] = f"platform/workload-accounts/{workload_name}"
    metadata["envs_path"] = f"workloads/{workload_name}"
    metadata["cidr_tier"] = cidr_tier
    metadata["vpc_cidr"] = vpc_cidr
    metadata["members"] = [
        {
            "email": member_email,
            "permissions": {env: "AdministratorAccess" for env in environments},
        }
    ] if member_email else []
    metadata["environments"] = env_map

    for old_field in ["project_name", "account_id", "account_email", "enabled_for_access", "deploy_role_ready"]:
        metadata.pop(old_field, None)

    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def create_workload_from_template(
    workload_template_dir: Path,
    platform_template_dir: Path,
    workload_target_dir: Path,
    platform_target_dir: Path,
    workload_name: str,
    environments: list[str],
    cidr_tier: str,
    vpc_cidr: str,
    env_emails: dict[str, str],
    member_email: str,
) -> None:
    if not workload_template_dir.exists():
        fail(f"template directory does not exist: {workload_template_dir}")
    if not platform_template_dir.exists():
        fail(f"template directory does not exist: {platform_template_dir}")
    if workload_target_dir.exists():
        fail(f"{workload_target_dir} already exists")
    if platform_target_dir.exists():
        fail(f"{platform_target_dir} already exists")

    shutil.copytree(workload_template_dir, workload_target_dir)
    shutil.copytree(platform_template_dir, platform_target_dir)
    replace_placeholders_in_text_files(workload_target_dir, workload_name, env_emails["prod"])
    replace_placeholders_in_text_files(platform_target_dir, workload_name, env_emails["prod"])
    update_metadata(workload_target_dir, workload_name, environments, cidr_tier, vpc_cidr, env_emails, member_email)


def main() -> None:
    workload_name, environments, cidr_tier, env_emails, member_email = parse_args()
    repo = repo_root_from_script()

    sys.path.insert(0, str(repo / "scripts"))
    import allocate_cidr  # noqa: E402

    workload_template_dir = repo / "workloads" / "_template"
    platform_template_dir = repo / "platform" / "workload-accounts" / "_template"
    workload_target_dir   = repo / "workloads" / workload_name
    platform_target_dir   = repo / "platform" / "workload-accounts" / workload_name

    registry_dir       = repo / ".repo-meta"
    registry_lock_path = registry_dir / "used_vpc_cidrs.lock"
    registry_dir.mkdir(parents=True, exist_ok=True)

    lock = FileLock(str(registry_lock_path))
    with lock:
        used = allocate_cidr.used_indices()
        if workload_name in {meta.get("workload_name") for _, meta in allocate_cidr.load_all_metadata()}:
            fail(f"workload '{workload_name}' already exists in the registry")

        idx  = allocate_cidr.next_free_index(cidr_tier, used)
        cidr = allocate_cidr.cidr_for_index(cidr_tier, idx)

        created = False
        try:
            create_workload_from_template(
                workload_template_dir=workload_template_dir,
                platform_template_dir=platform_template_dir,
                workload_target_dir=workload_target_dir,
                platform_target_dir=platform_target_dir,
                workload_name=workload_name,
                environments=environments,
                cidr_tier=cidr_tier,
                vpc_cidr=cidr,
                env_emails=env_emails,
                member_email=member_email,
            )
            created = True
            allocate_cidr.write_csv(allocate_cidr.build_csv_rows())
        except Exception:
            if not created:
                for d in [workload_target_dir, platform_target_dir]:
                    if d.exists():
                        shutil.rmtree(d)
            raise

    print(f"Created {workload_target_dir}")
    print(f"Tier {cidr_tier}, index {idx} → {cidr}")
    print(f"Environments: {', '.join(environments)}")
    for env_name in environments:
        print(f"  {env_name}: email={env_emails[env_name]}")


if __name__ == "__main__":
    main()
