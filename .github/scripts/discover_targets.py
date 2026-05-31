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

projects_dir = repo / "projects"
for metadata_file in sorted(projects_dir.glob("*/metadata.json")):
    if metadata_file.parent.name == "_template":
        continue
    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    project_name = metadata["project_name"]

    for env_name, env_cfg in metadata.get("environments", {}).items():
        targets.append({
            "name": f"projects/{project_name}/bootstrap:{env_name}",
            "path": metadata["account_bootstrap_path"],
            "kind": "project-bootstrap",
            "project_name": project_name,
            "environment": env_name,
            "account_id": env_cfg.get("account_id", ""),
            "deploy_role_ready": env_cfg.get("deploy_role_ready", False),
        })
        if not metadata.get("terraform_repo"):
            targets.append({
                "name": f"projects/{project_name}/envs:{env_name}",
                "path": metadata["envs_path"],
                "kind": "project",
                "project_name": project_name,
                "environment": env_name,
                "vpc_cidr": env_cfg.get("vpc_cidr", ""),
            })

print(json.dumps(targets))
