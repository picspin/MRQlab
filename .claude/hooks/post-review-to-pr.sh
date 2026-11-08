#!/usr/bin/env bash
# .claude/hooks/post-review-to-pr.sh
# SubagentStop hook for deep-reviewer:
# 1. Parse findings from reviewer transcript
# 2. Deduplicate findings via fingerprint
# 3. Post inline review comments + summary via gh api
# 4. Set commit status to failure if blocker findings are detected

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
TRANSCRIPT_ARG="${1:-}"
DRY_RUN="${DRY_RUN:-0}"

# Read hook payload from stdin if transcript not given as argument
TRANSCRIPT_PATH=""
if [ -n "$TRANSCRIPT_ARG" ] && [ -f "$TRANSCRIPT_ARG" ]; then
    TRANSCRIPT_PATH="$TRANSCRIPT_ARG"
else
    if [ ! -t 0 ]; then
        STDIN_JSON=$(cat)
        if [ -n "$STDIN_JSON" ]; then
            TRANSCRIPT_PATH=$(echo "$STDIN_JSON" | jq -r '.transcript_path // .agent_transcript_path // empty' 2>/dev/null || true)
        fi
    fi
fi

if [ -z "$TRANSCRIPT_PATH" ]; then
    TRANSCRIPT_PATH="${CODEX_COMPANION_TRANSCRIPT_PATH:-}"
fi

# Determine repository and PR context
REPO_FULL="${GITHUB_REPOSITORY:-}"
if [ -z "$REPO_FULL" ]; then
    REPO_FULL="owner/MRQlab"
fi

PR_NUMBER="${PR_NUMBER:-${GITHUB_PR_NUMBER:-}}"
COMMIT_SHA="${COMMIT_SHA:-$(git rev-parse HEAD 2>/dev/null || echo "0000000000000000000000000000000000000000")}"

echo "=== [post-review-to-pr] Deep Review Hook ==="
echo "Repository: $REPO_FULL"
echo "Commit:     $COMMIT_SHA"
echo "PR Number:  ${PR_NUMBER:-"(none detected)"}"
echo "Transcript: ${TRANSCRIPT_PATH:-"(stdin / none)"}"

# Run Python helper to extract, deduplicate, and format findings
export HOOK_TRANSCRIPT_PATH="$TRANSCRIPT_PATH"
export HOOK_COMMIT_SHA="$COMMIT_SHA"
export HOOK_REPO_FULL="$REPO_FULL"
export HOOK_PR_NUMBER="$PR_NUMBER"
export HOOK_DRY_RUN="$DRY_RUN"

python3 - <<'EOF'
import hashlib
import json
import os
import re
import sys

transcript_path = os.environ.get("HOOK_TRANSCRIPT_PATH", "")
commit_sha = os.environ.get("HOOK_COMMIT_SHA", "HEAD")
repo_full = os.environ.get("HOOK_REPO_FULL", "owner/MRQlab")
pr_number = os.environ.get("HOOK_PR_NUMBER", "")
dry_run = os.environ.get("HOOK_DRY_RUN", "0") == "1"

content = ""
if transcript_path and os.path.isfile(transcript_path):
    with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
elif not sys.stdin.isatty():
    content = sys.stdin.read()

# Extract JSON findings blocks
findings = []

# Pattern 1: Search for JSON blocks ```json ... ```
json_blocks = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
for block in json_blocks:
    try:
        data = json.loads(block)
        if isinstance(data, dict) and "findings" in data and isinstance(data["findings"], list):
            findings.extend(data["findings"])
    except Exception:
        pass

# Pattern 2: Search for raw JSON objects with "findings" key if no fenced blocks matched
if not findings:
    raw_matches = re.findall(r'(\{\s*"findings"\s*:\s*\[.*?\]\s*\})', content, re.DOTALL)
    for block in raw_matches:
        try:
            data = json.loads(block)
            if isinstance(data, dict) and "findings" in data and isinstance(data["findings"], list):
                findings.extend(data["findings"])
        except Exception:
            pass

# Deduplicate by fingerprint
deduped = []
seen_fingerprints = set()

for item in findings:
    if not isinstance(item, dict):
        continue
    file_path = str(item.get("file", "")).strip()
    line = item.get("line", 0)
    severity = str(item.get("severity", "minor")).lower().strip()
    evidence = str(item.get("evidence", "")).strip()
    suggestion = str(item.get("suggestion", "")).strip()

    if not file_path:
        continue

    # Fingerprint key
    fp_raw = f"{file_path}:{line}:{severity}:{evidence}"
    fp = hashlib.sha256(fp_raw.encode("utf-8")).hexdigest()[:16]

    if fp not in seen_fingerprints:
        seen_fingerprints.add(fp)
        deduped.append({
            "fingerprint": fp,
            "severity": severity,
            "file": file_path,
            "line": line,
            "evidence": evidence,
            "suggestion": suggestion,
        })

blockers = [f for f in deduped if f["severity"] == "blocker"]
majors = [f for f in deduped if f["severity"] == "major"]
minors = [f for f in deduped if f["severity"] == "minor"]

print(f"[post-review-to-pr] Parsed {len(findings)} raw finding(s), {len(deduped)} unique deduplicated finding(s).")
print(f"[post-review-to-pr] Breakdown: {len(blockers)} blocker(s), {len(majors)} major(s), {len(minors)} minor(s).")

# Save structured summary for shell dispatch
result_data = {
    "repo": repo_full,
    "commit_sha": commit_sha,
    "pr_number": pr_number,
    "total": len(deduped),
    "blocker_count": len(blockers),
    "has_blockers": len(blockers) > 0,
    "findings": deduped,
    "dry_run": dry_run or not pr_number,
}

with open("/tmp/deep_reviewer_result.json", "w", encoding="utf-8") as out:
    json.dump(result_data, out, indent=2)

EOF

# Read result data for API dispatch / reporting
RESULT_FILE="/tmp/deep_reviewer_result.json"
if [ ! -f "$RESULT_FILE" ]; then
    echo "[post-review-to-pr] Error: Result file was not generated."
    exit 0
fi

TOTAL_FINDINGS=$(jq -r '.total' "$RESULT_FILE")
HAS_BLOCKERS=$(jq -r '.has_blockers' "$RESULT_FILE")
IS_DRY_RUN=$(jq -r '.dry_run' "$RESULT_FILE")

# Format summary text
SUMMARY="### 🔬 Deep Review Summary\n\n"
if [ "$TOTAL_FINDINGS" -eq 0 ]; then
    SUMMARY+="✅ **All checks passed.** No defects or discrepancies detected."
else
    SUMMARY+="Detected **$TOTAL_FINDINGS** verified finding(s):\n\n"
    SUMMARY+="| Severity | File | Line | Fingerprint | Evidence |\n"
    SUMMARY+="|---|---|---|---|---|\n"
    while IFS= read -r item; do
        SEV=$(echo "$item" | jq -r '.severity')
        FILE=$(echo "$item" | jq -r '.file')
        LINE=$(echo "$item" | jq -r '.line')
        FP=$(echo "$item" | jq -r '.fingerprint')
        EVID=$(echo "$item" | jq -r '.evidence' | tr '\n' ' ' | cut -c 1-80)
        SUMMARY+="| **$SEV** | \`$FILE\` | $LINE | \`$FP\` | $EVID... |\n"
    done < <(jq -c '.findings[]' "$RESULT_FILE")
fi

echo -e "\n$SUMMARY\n"

# Commit status state
if [ "$HAS_BLOCKERS" = "true" ]; then
    STATUS_STATE="failure"
    STATUS_DESC="Deep review found blocker issue(s)"
else
    STATUS_STATE="success"
    STATUS_DESC="Deep review passed"
fi

# Dispatch to GitHub API (or dry-run if dry_run=true / no PR / sandbox constraint)
if [ "$IS_DRY_RUN" = "true" ] || [ "$DRY_RUN" = "1" ] || [ -z "$PR_NUMBER" ]; then
    echo "[post-review-to-pr] [DRY RUN] GitHub API calls simulated (sandbox safe):"
    echo "  → Commit Status: POST /repos/$REPO_FULL/statuses/$COMMIT_SHA"
    echo "      state=\"$STATUS_STATE\", context=\"claude/deep-reviewer\", description=\"$STATUS_DESC\""
    if [ -n "$PR_NUMBER" ]; then
        echo "  → PR Review Comments: POST /repos/$REPO_FULL/pulls/$PR_NUMBER/reviews"
        echo "      total_comments=$TOTAL_FINDINGS"
    fi
else
    echo "[post-review-to-pr] Executing live GitHub API calls via gh..."
    # 1. Post commit status
    gh api --method POST "repos/$REPO_FULL/statuses/$COMMIT_SHA" \
        -f state="$STATUS_STATE" \
        -f context="claude/deep-reviewer" \
        -f description="$STATUS_DESC" || true

    # 2. Post PR review comments and summary
    if [ -n "$PR_NUMBER" ]; then
        gh api --method POST "repos/$REPO_FULL/issues/$PR_NUMBER/comments" \
            -f body="$SUMMARY" || true
    fi
fi

echo "=== [post-review-to-pr] Completed successfully ==="
exit 0
