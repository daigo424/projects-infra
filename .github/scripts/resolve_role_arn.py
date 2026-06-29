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

workload_name = target.get("workload_name")
if not workload_name:
    print("Missing workload_name in target metadata", file=sys.stderr)
    sys.exit(1)

env_name = target.get("environment", "prod")

metadata_path = repo / "workloads" / workload_name / "metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

env_cfg = metadata.get("environments", {}).get(env_name, {})

if target["kind"] == "workload-bootstrap" and not env_cfg.get("deploy_role_ready"):
    platform = json.loads((repo / "platform" / "metadata.json").read_text(encoding="utf-8"))
    print(f"arn:aws:iam::{platform['management_account_id']}:role/{platform['platform_role_name']}")
    sys.exit(0)

account_id = env_cfg.get("account_id", "")
role_name = metadata.get("role_name", "")

if not account_id or len(account_id) != 12:
    if not env_cfg.get("deploy_role_ready", False):
        print(
            f"Workload '{workload_name}' env '{env_name}' is not ready yet "
            f"(deploy_role_ready=false). Run the account-bootstrap apply first.",
            file=sys.stderr,
        )
    else:
        print(f"Invalid account_id '{account_id}' for workload '{workload_name}' env '{env_name}'", file=sys.stderr)
    sys.exit(1)
if not role_name:
    print(f"Missing role_name for workload {workload_name}", file=sys.stderr)
    sys.exit(1)

print(f"arn:aws:iam::{account_id}:role/{role_name}")
