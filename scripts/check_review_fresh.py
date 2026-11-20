#!/usr/bin/env python3
"""check_review_fresh.py: verify a deep-review report is still bound to HEAD.

Usage: check_review_fresh.py reviews/review-<sha>.json

FRESH (exit 0) only when review_sha equals the current HEAD and stale is not true.
Anything else prints STALE and exits 1. Check this before citing any review finding.
"""

import json
import subprocess
import sys


def current_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} reviews/review-<sha>.json", file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            report = json.load(f)
    except FileNotFoundError:
        print(f"STALE: report not found: {sys.argv[1]}")
        return 1
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"STALE: report not readable JSON: {sys.argv[1]} ({e})")
        return 1
    if not isinstance(report, dict):
        print(f"STALE: report not a JSON object: {sys.argv[1]}")
        return 1
    review_sha = report.get("review_sha", "")
    head = current_head()
    if report.get("stale") is True:
        print(f"STALE: report stale flag set (review_sha={review_sha}, HEAD={head})")
        return 1
    if review_sha != head:
        print(f"STALE: review_sha={review_sha}, HEAD={head}")
        return 1
    print("FRESH")
    return 0


if __name__ == "__main__":
    sys.exit(main())
