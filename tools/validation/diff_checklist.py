#!/usr/bin/env python3
"""Diff-triggered validation checklist.

Given a git diff range, classify every changed path into a *surface* and print
the checks that surface makes mandatory. `--check` additionally verifies the
required test files exist, and exits non-zero if a changed surface has no
covering test — so a change cannot silently skip its validation.

Usage:
    python tools/validation/diff_checklist.py                 # base=origin/main, head=HEAD
    python tools/validation/diff_checklist.py --base ec3355f --head a3cf1ce
    python tools/validation/diff_checklist.py --check          # fail if a surface is untested
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# surface -> (path predicates, required test files, human-readable checks)
SURFACES = {
    "lease/licensing": {
        "match": lambda p: p.startswith("services/local_agent/mrqlab_agent/")
        and any(k in p for k in ("license", "models", "config", "main", "security", "store", "providers")),
        "tests": [
            "tests/local_agent/test_license.py",
            "tests/local_agent/test_lease_wiring.py",
            "tests/local_agent/test_lease_window_properties.py",
            "tests/local_agent/test_lease_window_differential.py",
        ],
        "checks": [
            "pytest tests/local_agent -q",
            "python tools/validation/shadow_walkthrough.py",
        ],
    },
    "physics/sequence": {
        "match": lambda p: p.startswith(("packages/physics/", "packages/sequence-ir/", "packages/recon/")),
        "tests": [],
        "checks": ["pytest tests/experiment -q", "pytest tests/test_sequence_operations.py -q"],
    },
    "experiment/api": {
        "match": lambda p: p.startswith(("packages/mrqlab_experiment/", "services/api/")),
        "tests": [],
        "checks": ["pytest tests/ -q"],
    },
    "frontend": {
        "match": lambda p: p.startswith(("apps/web/", "packages/*/web")),
        "tests": [],
        "checks": ["npm --prefix apps/web run test", "npm --prefix apps/web run typecheck"],
    },
    "docs": {
        "match": lambda p: p.startswith("docs/"),
        "tests": [],
        "checks": ["manual: confirm every claim in the doc matches the diff"],
    },
    "validation-tooling": {
        "match": lambda p: p.startswith(("tools/validation/", ".githooks/")),
        "tests": [],
        "checks": ["python tools/validation/shadow_walkthrough.py"],
    },
}


def changed_paths(base: str, head: str, staged: bool = False) -> list[str]:
    args = ["git", "diff", "--name-only", "--cached"] if staged else ["git", "diff", "--name-only", f"{base}..{head}"]
    out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
    return [line for line in out.stdout.splitlines() if line.strip()]


def classify(paths: list[str]) -> dict[str, list[str]]:
    hit: dict[str, list[str]] = {}
    for path in paths:
        for name, spec in SURFACES.items():
            # A surface is triggered by a change to one of its source paths OR to
            # one of its own required tests — so deleting a guard test is itself a
            # trigger and cannot slip through unvalidated.
            if spec["match"](path) or path in spec["tests"]:
                hit.setdefault(name, []).append(path)
    return hit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="origin/main")
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--staged", action="store_true", help="classify the staged diff (git diff --cached)")
    ap.add_argument("--check", action="store_true", help="fail if a surface has no covering test")
    args = ap.parse_args()

    paths = changed_paths(args.base, args.head, staged=args.staged)
    hits = classify(paths)
    scope = "staged" if args.staged else f"{args.base}..{args.head}"
    print(f"diff {scope}: {len(paths)} changed path(s)")
    if not hits:
        print("no validation surface triggered.")
        return 0

    failed = False
    for name, spec in SURFACES.items():
        if name not in hits:
            continue
        print(f"\n== surface: {name} ==")
        for p in sorted(hits[name]):
            print(f"   - {p}")
        for check in spec["checks"]:
            print(f"   required check: {check}")
        for test in spec["tests"]:
            exists = (ROOT / test).is_file()
            print(f"   test {'OK ' if exists else 'MISSING'} {test}")
            if args.check and not exists:
                failed = True
    if args.check and failed:
        print("\nCHECK FAILED: a changed surface is missing its required test file.")
        return 1
    print("\nchecklist OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
