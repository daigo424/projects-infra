#!/usr/bin/env python3
import csv
import ipaddress
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


def parse_args() -> tuple[str, list[str], dict[str, str], dict[str, str]]:
    if len(sys.argv) < 5:
        fail(
            "usage: new_project.py <project-name> <environments> <prod-cidr> <prod-email>"
            " [<test-email>]",
            exit_code=2,
        )

    project_name = sys.argv[1].strip()
    environments = [e.strip() for e in sys.argv[2].split(",")]
    cidr    = sys.argv[3].strip()
    prod_email   = sys.argv[4].strip()
    test_email   = sys.argv[5].strip() if len(sys.argv) > 5 else ""

    if not project_name:
        fail("project-name must not be empty")

    valid_envs = {"prod", "test"}
    for env in environments:
        if env not in valid_envs:
            fail(f"unknown environment '{env}'. Must be one of: {', '.join(sorted(valid_envs))}")

    env_cidrs: dict[str, str] = {"prod": cidr}
    env_emails: dict[str, str] = {"prod": prod_email}

    if "test" in environments:
        if not test_email:
            fail("test-email is required when environments includes 'test'")
        env_cidrs["test"] = cidr
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

    return project_name, environments, env_cidrs, env_emails


def repo_root_from_script() -> Path:
    return Path(__file__).resolve().parents[2]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_registry_csv(csv_path: Path) -> None:
    if csv_path.exists():
        return

    ensure_dir(csv_path.parent)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["project_name", "account_email", "vpc_cidr"])


def parse_network(cidr: str) -> ipaddress.IPv4Network:
    try:
        network = ipaddress.ip_network(cidr, strict=True)
    except ValueError as exc:
        fail(f"invalid CIDR '{cidr}': {exc}")

    if not isinstance(network, ipaddress.IPv4Network):
        fail(f"only IPv4 CIDR is supported: {cidr}")

    return network


def load_registry_rows(csv_path: Path) -> list[dict[str, str]]:
    ensure_registry_csv(csv_path)

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        expected = {"project_name", "account_email", "vpc_cidr"}
        if not reader.fieldnames or not expected.issubset(set(reader.fieldnames)):
            fail(
                f"registry file '{csv_path}' must have columns: "
                "project_name, account_email, vpc_cidr"
            )

        rows: list[dict[str, str]] = []
        for row in reader:
            rows.append(
                {
                    "project_name": (row.get("project_name") or "").strip(),
                    "account_email": (row.get("account_email") or "").strip(),
                    "vpc_cidr": (row.get("vpc_cidr") or "").strip(),
                }
            )
        return rows


def validate_registry_conflicts(
    rows: list[dict[str, str]],
    new_project_name: str,
    new_account_email: str,
    new_network: ipaddress.IPv4Network,
) -> None:
    for row in rows:
        existing_project = row["project_name"]
        existing_email = row["account_email"]
        existing_cidr = row["vpc_cidr"]

        if not existing_project and not existing_email and not existing_cidr:
            continue

        if existing_project == new_project_name:
            fail(
                "project_name already registered in CIDR registry:\n"
                f"  project_name: {existing_project}"
            )

        if not existing_cidr:
            fail(
                "registry contains a row with empty vpc_cidr:\n"
                f"  project_name: {existing_project}\n"
                f"  account_email: {existing_email}"
            )

        try:
            existing_network = ipaddress.ip_network(existing_cidr, strict=True)
        except ValueError as exc:
            fail(
                "invalid CIDR found in registry:\n"
                f"  project_name : {existing_project}\n"
                f"  account_email: {existing_email}\n"
                f"  vpc_cidr     : {existing_cidr}\n"
                f"  error        : {exc}"
            )

        if not isinstance(existing_network, ipaddress.IPv4Network):
            fail(
                "registry contains non-IPv4 CIDR:\n"
                f"  project_name: {existing_project}\n"
                f"  vpc_cidr    : {existing_cidr}"
            )

        if new_network.overlaps(existing_network):
            fail(
                "CIDR overlap detected:\n"
                f"  requested_project : {new_project_name}\n"
                f"  requested_email   : {new_account_email}\n"
                f"  requested_cidr    : {new_network}\n"
                f"  existing_project  : {existing_project}\n"
                f"  existing_email    : {existing_email}\n"
                f"  existing_cidr     : {existing_network}"
            )


def register_cidr(
    csv_path: Path,
    project_name: str,
    account_email: str,
    network: ipaddress.IPv4Network,
) -> None:
    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([project_name, account_email, str(network)])


def replace_placeholders_in_text_files(
    target_dir: Path,
    project_name: str,
    prod_email: str,
) -> None:
    replacements = {
        "__PROJECT_NAME__": project_name,
        "__PROJECT_EMAIL__": prod_email,
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
    project_name: str,
    environments: list[str],
    env_cidrs: dict[str, str],
    env_emails: dict[str, str],
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
            "vpc_cidr": env_cidrs[env_name],
            "enabled_for_access": True,
            "deploy_role_ready": False,
        }

    metadata["project_name"] = project_name
    metadata["display_name"] = project_name
    metadata["account_bootstrap_path"] = f"projects/{project_name}/account-bootstrap"
    metadata["envs_path"] = f"projects/{project_name}/envs"
    metadata["environments"] = env_map

    for old_field in ["account_id", "account_email", "enabled_for_access", "deploy_role_ready", "prod_path"]:
        metadata.pop(old_field, None)

    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def create_project_from_template(
    template_dir: Path,
    target_dir: Path,
    project_name: str,
    environments: list[str],
    env_cidrs: dict[str, str],
    env_emails: dict[str, str],
) -> None:
    if not template_dir.exists():
        fail(f"template directory does not exist: {template_dir}")

    if not template_dir.is_dir():
        fail(f"template path is not a directory: {template_dir}")

    if target_dir.exists():
        fail(f"{target_dir} already exists")

    shutil.copytree(template_dir, target_dir)
    replace_placeholders_in_text_files(target_dir, project_name, env_emails["prod"])
    update_metadata(target_dir, project_name, environments, env_cidrs, env_emails)


def main() -> None:
    project_name, environments, env_cidrs, env_emails = parse_args()
    repo = repo_root_from_script()

    template_dir = repo / "projects" / "_template"
    target_dir = repo / "projects" / project_name

    registry_dir = repo / ".repo-meta"
    registry_csv_path = registry_dir / "used_vpc_cidrs.csv"
    registry_lock_path = registry_dir / "used_vpc_cidrs.lock"

    env_networks = {env: parse_network(cidr) for env, cidr in env_cidrs.items()}

    ensure_dir(registry_dir)
    lock = FileLock(str(registry_lock_path))

    with lock:
        rows = load_registry_rows(registry_csv_path)

        for env, network in env_networks.items():
            validate_registry_conflicts(
                rows, f"{project_name}-{env}", env_emails[env], network
            )

        created = False
        try:
            create_project_from_template(
                template_dir=template_dir,
                target_dir=target_dir,
                project_name=project_name,
                environments=environments,
                env_cidrs={env: str(net) for env, net in env_networks.items()},
                env_emails=env_emails,
            )
            created = True

            for env, network in env_networks.items():
                register_cidr(
                    csv_path=registry_csv_path,
                    project_name=f"{project_name}-{env}",
                    account_email=env_emails[env],
                    network=network,
                )
        except Exception:
            if created and target_dir.exists():
                shutil.rmtree(target_dir)
            raise

    print(f"Created {target_dir}")
    print(f"Environments: {', '.join(environments)}")
    for env_name in environments:
        print(f"  {env_name}: cidr={env_cidrs[env_name]}  email={env_emails[env_name]}")


if __name__ == "__main__":
    main()
