#!/usr/bin/env python3
import json
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("usage: resolve_role_arn.py '<target_json>'", file=sys.stderr)
    sys.exit(2)

repo = Path(__file__).resolve().parents[2]
target = json.loads(sys.argv[1])

if target["kind"] in ["platform", "platform-bootstrap"]:
    metadata = json.loads((repo / "platform" / "metadata.json").read_text(encoding="utf-8"))
    account_id = metadata["management_account_id"]
    role_name = metadata["platform_role_name"]
    print(f"arn:aws:iam::{account_id}:role/{role_name}")
    sys.exit(0)

project_name = target.get("project_name")
if not project_name:
    print("Missing project_name in target metadata", file=sys.stderr)
    sys.exit(1)

metadata_path = repo / "projects" / project_name / "metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

if target["kind"] == "project-bootstrap":
    platform = json.loads((repo / "platform" / "metadata.json").read_text(encoding="utf-8"))
    print(f"arn:aws:iam::{platform['management_account_id']}:role/{platform['platform_role_name']}")
    sys.exit(0)

account_id = metadata.get("account_id", "")
role_name = metadata.get("role_name", "")
if not account_id or len(account_id) != 12:
    print(f"Invalid account_id for project {project_name}", file=sys.stderr)
    sys.exit(1)
if not role_name:
    print(f"Missing role_name for project {project_name}", file=sys.stderr)
    sys.exit(1)

print(f"arn:aws:iam::{account_id}:role/{role_name}")
