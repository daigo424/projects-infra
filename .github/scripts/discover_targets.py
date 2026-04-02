#!/usr/bin/env python3
import json
from pathlib import Path

repo = Path(__file__).resolve().parents[2]

targets = [
    {
        "name": "platform-bootstrap",
        "path": "platform/bootstrap",
        "kind": "platform-bootstrap"
    },
    {
        "name": "platform-identity",
        "path": "platform/identity",
        "kind": "platform"
    },
    {
        "name": "platform-accounts",
        "path": "platform/accounts",
        "kind": "platform"
    },
    {
        "name": "platform-access",
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
    targets.append({
        "name": f"{project_name}-account-bootstrap",
        "path": metadata["account_bootstrap_path"],
        "kind": "project-bootstrap",
        "project_name": project_name
    })
    targets.append({
        "name": f"{project_name}-prod",
        "path": metadata["prod_path"],
        "kind": "project",
        "project_name": project_name
    })

print(json.dumps(targets))
