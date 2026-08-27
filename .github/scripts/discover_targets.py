#!/usr/bin/env python3
import json
from pathlib import Path

repo = Path(__file__).resolve().parents[2]

targets = [
    {
        "name": "platform/bootstrap",
        "path": "platform/bootstrap",
        "kind": "platform-bootstrap"
    },
    {
        "name": "platform/identity",
        "path": "platform/identity",
        "kind": "platform"
    },
    {
        "name": "platform/accounts",
        "path": "platform/accounts",
        "kind": "platform"
    },
    {
        "name": "platform/access",
        "path": "platform/access",
        "kind": "platform"
    },
]

workloads_dir = repo / "workloads"
for metadata_file in sorted(workloads_dir.glob("*/metadata.json")):
    if metadata_file.parent.name.startswith("_"):
        continue
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    workload_name = metadata["workload_name"]

    for env_name, env_cfg in metadata.get("environments", {}).items():
        targets.append({
            "name": f"workloads/{workload_name}/account-bootstrap:{env_name}",
            "path": metadata["account_bootstrap_path"],
            "kind": "workload-bootstrap",
            "workload_name": workload_name,
            "environment": env_name,
            "account_id": env_cfg.get("account_id", ""),
            "deploy_role_ready": env_cfg.get("deploy_role_ready", False),
            "additional_github_repos": metadata.get("additional_github_repos", []),
        })
        targets.append({
            "name": f"workloads/{workload_name}:{env_name}",
            "path": metadata["envs_path"],
            "kind": "workload",
            "workload_name": workload_name,
            "environment": env_name,
            "account_id": env_cfg.get("account_id", ""),
            "vpc_cidr": metadata.get("vpc_cidr", ""),
            "deploy_role_ready": env_cfg.get("deploy_role_ready", False),
        })

print(json.dumps(targets))
