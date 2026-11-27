#!/usr/bin/env python3
"""Check staged whitespace and print review prompts for affected areas."""
import subprocess
import sys


def git(*args):
    return subprocess.run(["git", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    result = git("diff", "--cached", "--check")
    if result.returncode:
        sys.stderr.buffer.write(result.stdout + result.stderr)
        return result.returncode
    result = git("diff", "--cached", "--name-only", "-z", "--no-renames")
    if result.returncode:
        sys.stderr.buffer.write(result.stderr)
        return result.returncode
    paths = result.stdout.decode("utf-8", "surrogateescape").split("\0")
    prompts = ["all changes: run relevant tests; inspect behavior, failure paths and compatibility"]
    if any(p.startswith(("packages/mrqlab_experiment/", "tests/experiment/")) for p in paths):
        prompts.append("clinical/experiment: contract, units, provenance, baseline and scientific boundaries")
    if any(p.startswith(("packages/physics/", "packages/recon/", "packages/sequence-ir/")) for p in paths):
        prompts.append("physics/sequence: independent reference, numerical limits and model assumptions")
    if any(p.startswith(("services/", "apps/")) for p in paths):
        prompts.append("service/UI: API compatibility, failure states and end-to-end behavior")
    if any(p.startswith(("scripts/", ".githooks/")) or p == "tests/test_staged_validation_hook.py" for p in paths):
        prompts.append("validation tooling: exercise the real hook in an isolated repository")
    print("Staged-diff review checklist (prompts, not proof of validation):", file=sys.stderr)
    for prompt in prompts:
        print(f"- {prompt}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
