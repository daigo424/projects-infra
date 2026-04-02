#!/usr/bin/env python3
import json
import shutil
import sys
from pathlib import Path

if len(sys.argv) != 4:
    print("usage: new_project.py <project-name> <account-email> <vpc-cidr>", file=sys.stderr)
    sys.exit(2)

project_name = sys.argv[1]
account_email = sys.argv[2]
vpc_cidr = sys.argv[3]

repo = Path(__file__).resolve().parents[2]
template_dir = repo / "projects" / "_template"
target_dir = repo / "projects" / project_name

if target_dir.exists():
    print(f"{target_dir} already exists", file=sys.stderr)
    sys.exit(1)

shutil.copytree(template_dir, target_dir)

for path in target_dir.rglob("*"):
    if path.is_file():
        content = path.read_text(encoding="utf-8")
        content = content.replace("__PROJECT_NAME__", project_name)
        content = content.replace("__PROJECT_EMAIL__", account_email)
        content = content.replace("__PROJECT_CIDR__", vpc_cidr)
        path.write_text(content, encoding="utf-8")

metadata_path = target_dir / "metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
metadata["project_name"] = project_name
metadata["display_name"] = project_name
metadata["account_email"] = account_email
metadata["account_bootstrap_path"] = f"projects/{project_name}/account-bootstrap"
metadata["prod_path"] = f"projects/{project_name}/envs/prod"
target_dir.joinpath("metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

print(f"Created {target_dir}")
