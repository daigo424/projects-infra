#!/usr/bin/env python3
import json
import sys

if len(sys.argv) != 3:
    print("usage: filter_changed_targets.py '<targets_json>' '<changed_files_json>'", file=sys.stderr)
    sys.exit(2)

targets = json.loads(sys.argv[1])
changed_files = json.loads(sys.argv[2])

matched = []
for target in targets:
    prefix = target["path"].rstrip("/") + "/"
    if any(f == target["path"] or f.startswith(prefix) for f in changed_files):
        matched.append(target)

print(json.dumps(matched))
