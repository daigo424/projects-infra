#!/usr/bin/env python3
"""VPC CIDR allocation tool.

Allocates CIDRs sequentially from tier-specific parent blocks.
One CIDR per project — shared across all environments (prod, test, etc.)

Tiers:
  A  10.0.0.0/11   → /16 per VPC  (max 32,   common infra)
  B  10.32.0.0/11  → /18 per VPC  (max 128,  large scale)
  C  10.64.0.0/10  → /20 per VPC  (max 1024, normal service) ← default
  D  10.128.0.0/10 → /22 per VPC  (max 4096, microservice)

Usage:
  python scripts/allocate_cidr.py list
  python scripts/allocate_cidr.py allocate --project <name> [--tier C]
  python scripts/allocate_cidr.py allocate --project <name> [--tier C] --dry-run
  python scripts/allocate_cidr.py sync-csv
"""

import argparse
import csv
import ipaddress
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
CSV_PATH = REPO_ROOT / ".repo-meta" / "used_vpc_cidrs.csv"
CSV_FIELDS = ["vpc_cidr", "tier", "project_name", "prod_account_email", "test_account_email"]

TIERS: dict[str, dict] = {
    "A": {"parent": "10.0.0.0/11",   "prefix": 16},
    "B": {"parent": "10.32.0.0/11",  "prefix": 18},
    "C": {"parent": "10.64.0.0/10",  "prefix": 20},
    "D": {"parent": "10.128.0.0/10", "prefix": 22},
}
TIER_ORDER = {t: i for i, t in enumerate(TIERS)}

DEFAULT_TIER = "C"


def cidr_for_index(tier: str, index: int) -> str:
    config = TIERS[tier]
    parent = ipaddress.ip_network(config["parent"])
    max_count = 2 ** (config["prefix"] - parent.prefixlen)
    if index >= max_count:
        raise ValueError(f"Index {index} exceeds max VPCs for Tier {tier} ({max_count})")
    subnet_size = 2 ** (32 - config["prefix"])
    addr = ipaddress.ip_address(int(parent.network_address) + index * subnet_size)
    return f"{addr}/{config['prefix']}"


def tier_and_index_for_cidr(cidr: str) -> tuple[str, int] | None:
    """Return (tier, index) if cidr belongs to a known tier block, else None."""
    try:
        net = ipaddress.ip_network(cidr, strict=True)
    except ValueError:
        return None
    for tier, config in TIERS.items():
        parent = ipaddress.ip_network(config["parent"])
        if net.prefixlen != config["prefix"]:
            continue
        if not net.subnet_of(parent):
            continue
        subnet_size = 2 ** (32 - config["prefix"])
        offset = int(net.network_address) - int(parent.network_address)
        if offset % subnet_size != 0:
            continue
        return tier, offset // subnet_size
    return None


def load_all_metadata() -> list[tuple[Path, dict]]:
    results = []
    for path in sorted((REPO_ROOT / "projects").glob("*/metadata.json")):
        if path.parent.name.startswith("_"):
            continue
        with open(path, encoding="utf-8") as f:
            results.append((path, json.load(f)))
    return results


def used_indices() -> dict[str, set[int]]:
    used: dict[str, set[int]] = {t: set() for t in TIERS}
    for _, meta in load_all_metadata():
        cidr = meta.get("vpc_cidr")
        if not cidr:
            continue
        result = tier_and_index_for_cidr(cidr)
        if result:
            tier, idx = result
            used[tier].add(idx)
    return used


def next_free_index(tier: str, used: dict[str, set[int]]) -> int:
    config = TIERS[tier]
    parent = ipaddress.ip_network(config["parent"])
    max_count = 2 ** (config["prefix"] - parent.prefixlen)
    for i in range(max_count):
        if i not in used[tier]:
            return i
    raise ValueError(f"No available CIDRs remaining in Tier {tier}")


def build_csv_rows() -> list[dict]:
    rows = []
    for _, meta in load_all_metadata():
        cidr = meta.get("vpc_cidr")
        if not cidr:
            continue
        result = tier_and_index_for_cidr(cidr)
        tier_s = result[0] if result else "?"
        envs = meta.get("environments", {})
        rows.append({
            "vpc_cidr": cidr,
            "tier": tier_s,
            "project_name": meta["project_name"],
            "prod_account_email": envs.get("prod", {}).get("account_email", ""),
            "test_account_email": envs.get("test", {}).get("account_email", ""),
        })
    rows.sort(key=lambda r: (
        TIER_ORDER.get(r["tier"], 99),
        ipaddress.ip_network(r["vpc_cidr"], strict=False).network_address,
    ))
    return rows


def write_csv(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Updated {CSV_PATH.relative_to(REPO_ROOT)}")


def cmd_list(_args) -> None:
    rows = build_csv_rows()
    col_widths = {f: len(f) for f in CSV_FIELDS}
    for r in rows:
        for f in CSV_FIELDS:
            col_widths[f] = max(col_widths[f], len(r[f]))

    header = "  ".join(f.ljust(col_widths[f]) for f in CSV_FIELDS)
    print(header)
    print("-" * len(header))
    for r in rows:
        print("  ".join(r[f].ljust(col_widths[f]) for f in CSV_FIELDS))


def cmd_sync_csv(_args) -> None:
    write_csv(build_csv_rows())


def cmd_allocate(args) -> None:
    metadata_path = REPO_ROOT / "projects" / args.project / "metadata.json"
    if not metadata_path.exists():
        sys.exit(f"Error: {metadata_path} not found")

    with open(metadata_path, encoding="utf-8") as f:
        meta = json.load(f)

    existing_cidr = meta.get("vpc_cidr")

    if existing_cidr and not args.force:
        print(f"'{args.project}' already has vpc_cidr={existing_cidr}")
        answer = input("Overwrite? [y/N] ").strip().lower()
        if answer != "y":
            sys.exit("Aborted.")

    used = used_indices()

    # Free the existing slot so it is not double-counted when overwriting
    if existing_cidr:
        result = tier_and_index_for_cidr(existing_cidr)
        if result:
            old_tier, old_idx = result
            used[old_tier].discard(old_idx)

    idx = next_free_index(args.tier, used)
    cidr = cidr_for_index(args.tier, idx)

    print(f"Tier {args.tier}, index {idx} → {cidr}  ({args.project})")

    if args.dry_run:
        print("[dry-run] No files written.")
        return

    meta["cidr_tier"] = args.tier
    meta["vpc_cidr"] = cidr
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Updated {metadata_path.relative_to(REPO_ROOT)}")

    write_csv(build_csv_rows())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="VPC CIDR allocation tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="Show all current CIDR allocations")
    sub.add_parser("sync-csv", help="Regenerate .repo-meta/used_vpc_cidrs.csv from metadata.json files")

    alloc = sub.add_parser("allocate", help="Allocate next CIDR for a project")
    alloc.add_argument("--project", required=True, help="Project name (directory under projects/)")
    alloc.add_argument("--tier", default=DEFAULT_TIER, choices=list(TIERS), help="Tier (default: C)")
    alloc.add_argument("--dry-run", action="store_true", help="Print result without writing")
    alloc.add_argument("--force", action="store_true", help="Skip confirmation when overwriting")

    args = parser.parse_args()
    {"list": cmd_list, "allocate": cmd_allocate, "sync-csv": cmd_sync_csv}[args.command](args)


if __name__ == "__main__":
    main()
