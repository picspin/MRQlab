#!/usr/bin/env python3
"""Diff-triggered validation checklist.

Given a git diff range, classify every changed path into a *surface* and report
the checks that surface makes mandatory.

Two distinct things are on offer, and the output never conflates them:

* ``--check`` verifies each triggered surface's *required test files exist*. It
  is an existence gate: it proves a surface's guard tests were not deleted, not
  that they pass. Its summary line says so.
* ``--run`` implies ``--check`` and additionally *executes* every triggered
  surface's executable checks (a check starting with ``manual:`` is reported and
  skipped, never silently treated as passing). It fails if any executable check
  returns non-zero.

Without either flag the tool only prints the classification.

Usage:
    python tools/validation/diff_checklist.py --staged            # classify the staged diff
    python tools/validation/diff_checklist.py --check             # + existence gate
    python tools/validation/diff_checklist.py --check --run       # + execute the checks
    python tools/validation/diff_checklist.py --base ec3355f --head ee7e1c3
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
        # ``__init__`` is included because the lease-compatibility axis is
        # defined by ``mrqlab_agent.__version__`` (``RUNTIME_VERSION`` derives
        # from it), so a change to that file changes enforced behaviour.
        "match": lambda p: p.startswith("services/local_agent/mrqlab_agent/")
        and any(k in p for k in ("license", "models", "config", "main", "security", "store", "providers", "__init__")),
        "tests": [
            "tests/local_agent/test_license.py",
            "tests/local_agent/test_lease_wiring.py",
            "tests/local_agent/test_lease_window_properties.py",
            "tests/local_agent/test_lease_window_differential.py",
            # The hook's own e2e smoke: deleting it must itself trigger the
            # surface, so the guard cannot be removed unnoticed.
            "tests/local_agent/test_precommit_hook.py",
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
        # A real predicate, not a glob: ``str.startswith`` never expands ``*``,
        # so a literal "packages/*/web" would match nothing. Frontend lives
        # under ``apps/web/`` and any ``packages/<x>/web/`` tree.
        "match": lambda p: p.startswith("apps/web/")
        or (p.startswith("packages/") and "/web/" in p),
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
        "tests": ["tests/test_diff_checklist.py"],
        "checks": [
            "pytest tests/test_diff_checklist.py -q",
            "python tools/validation/shadow_walkthrough.py",
        ],
    },
}


def changed_paths(base: str, head: str, staged: bool = False) -> list[str]:
    args = ["git", "diff", "--name-only", "--cached"] if staged else ["git", "diff", "--name-only", f"{base}..{head}"]
    try:
        out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        scope = "the staged diff" if staged else f"{base}..{head}"
        detail = (exc.stderr or "").strip().splitlines()
        # Git's last line is often only generic usage. Keep the first diagnostic
        # too (normally "ambiguous argument … unknown revision") so callers can
        # repair an absent base without reproducing a traceback.
        useful = next((line for line in detail if "ambiguous argument" in line or "unknown revision" in line), None)
        hint = useful or (detail[-1] if detail else "git diff failed")
        raise SystemExit(f"diff_checklist: cannot read {scope}: {hint}")
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


def _run_checks(hits: dict[str, list[str]]) -> bool:
    """Execute every triggered surface's executable checks. True iff all pass."""
    ok = True
    for name, spec in SURFACES.items():
        if name not in hits:
            continue
        for check in spec["checks"]:
            if check.startswith("manual:"):
                print(f"   NOTE {check} (not executed by this tool)")
                continue
            # Run Python checks through the interpreter that launched this tool.
            # The hook deliberately selects a venv-capable interpreter; invoking
            # bare `python`/`pytest` here would silently discard that selection
            # (and breaks minimal PATH smoke repositories).
            command = check
            if check.startswith("pytest "):
                command = f"{sys.executable} -m {check}"
            elif check.startswith("python "):
                command = f"{sys.executable} {check.removeprefix('python ')}"
            print(f"   run  {check}")
            result = subprocess.run(command, shell=True, cwd=ROOT)
            if result.returncode != 0:
                print(f"   FAIL {check} (exit {result.returncode})")
                ok = False
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--base",
        help="base revision for a non-staged diff (required unless --staged is used)",
    )
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--staged", action="store_true", help="classify the staged diff (git diff --cached)")
    ap.add_argument("--check", action="store_true", help="verify each triggered surface's required test files exist")
    ap.add_argument("--run", action="store_true", help="execute each triggered surface's checks (implies --check)")
    args = ap.parse_args()
    if not args.staged and not args.base:
        ap.error("--base is required unless --staged is used (for example: --base $(git merge-base HEAD origin/main))")

    paths = changed_paths(args.base or "", args.head, staged=args.staged)
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

    if (args.check or args.run) and failed:
        print("\nCHECK FAILED: a changed surface is missing its required test file.")
        return 1

    if args.check or args.run:
        print("\nexistence check OK: every triggered surface's required test files are present.")
        if not args.run:
            print("(this is an existence gate only; the checks above were not executed by this tool)")
    if args.run:
        print("\nrunning the triggered surfaces' checks:")
        if not _run_checks(hits):
            print("\nCHECK FAILED: a triggered surface's check did not pass.")
            return 1
        print("\nall triggered checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
