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


def parse_args() -> tuple[str, str, str, list[str]]:
    if len(sys.argv) < 4:
        fail("usage: new_project.py <project-name> <account-email> <vpc-cidr> [environments]", exit_code=2)

    project_name  = sys.argv[1].strip()
    account_email = sys.argv[2].strip()
    vpc_cidr      = sys.argv[3].strip()
    environments  = [e.strip() for e in sys.argv[4].split(",")] if len(sys.argv) > 4 else ["prod"]

    if not project_name:
        fail("project-name must not be empty")

    if not account_email:
        fail("account-email must not be empty")

    if "@" not in account_email:
        fail(f"invalid account email: {account_email}")

    if not vpc_cidr:
        fail("vpc-cidr must not be empty")

    valid_envs = {"prod", "test"}
    for env in environments:
        if env not in valid_envs:
            fail(f"unknown environment '{env}'. Must be one of: {', '.join(sorted(valid_envs))}")

    return project_name, account_email, vpc_cidr, environments


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


def derive_env_email(base_email: str, project_name: str, env_name: str) -> str:
    local, domain = base_email.rsplit("@", 1)
    return f"{local}+{project_name}-{env_name}@{domain}"


def replace_placeholders_in_text_files(
    target_dir: Path,
    project_name: str,
    account_email: str,
    vpc_cidr: str,
) -> None:
    replacements = {
        "__PROJECT_NAME__": project_name,
        "__PROJECT_EMAIL__": account_email,
        "__PROJECT_CIDR__": vpc_cidr,
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
    account_email: str,
    environments: list[str],
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
            "account_email": derive_env_email(account_email, project_name, env_name),
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
    account_email: str,
    vpc_cidr: str,
    environments: list[str],
) -> None:
    if not template_dir.exists():
        fail(f"template directory does not exist: {template_dir}")

    if not template_dir.is_dir():
        fail(f"template path is not a directory: {template_dir}")

    if target_dir.exists():
        fail(f"{target_dir} already exists")

    shutil.copytree(template_dir, target_dir)
    replace_placeholders_in_text_files(target_dir, project_name, account_email, vpc_cidr)
    update_metadata(target_dir, project_name, account_email, environments)


def main() -> None:
    project_name, account_email, vpc_cidr, environments = parse_args()
    repo = repo_root_from_script()

    template_dir = repo / "projects" / "_template"
    target_dir = repo / "projects" / project_name

    registry_dir = repo / ".repo-meta"
    registry_csv_path = registry_dir / "used_vpc_cidrs.csv"
    registry_lock_path = registry_dir / "used_vpc_cidrs.lock"

    new_network = parse_network(vpc_cidr)

    ensure_dir(registry_dir)
    lock = FileLock(str(registry_lock_path))

    with lock:
        rows = load_registry_rows(registry_csv_path)
        validate_registry_conflicts(rows, project_name, account_email, new_network)

        created = False
        try:
            create_project_from_template(
                template_dir=template_dir,
                target_dir=target_dir,
                project_name=project_name,
                account_email=account_email,
                vpc_cidr=str(new_network),
                environments=environments,
            )
            created = True

            register_cidr(
                csv_path=registry_csv_path,
                project_name=project_name,
                account_email=account_email,
                network=new_network,
            )
        except Exception:
            if created and target_dir.exists():
                shutil.rmtree(target_dir)
            raise

    print(f"Created {target_dir}")
    print(f"Registered CIDR {new_network} in {registry_csv_path}")
    print(f"Environments: {', '.join(environments)}")
    for env_name in environments:
        print(f"  {env_name}: {derive_env_email(account_email, project_name, env_name)}")


if __name__ == "__main__":
    main()
