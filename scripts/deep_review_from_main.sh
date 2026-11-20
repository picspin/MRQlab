#!/usr/bin/env bash
# deep_review_from_main.sh: the single entry point for deep-review.
#
# Takes the reviewer rules from the main branch (never the working tree), builds
# a review prompt with the base sha and scope, runs one `claude -p` dispatch, and
# writes findings to reviews/review-<review_sha>.json.
#
# Usage: scripts/deep_review_from_main.sh [review-scope]
#   review-scope defaults to merge-base(main, HEAD)..HEAD.
# Requires: git repo, a readable `main` containing .claude/agents/deep-reviewer.md, claude CLI.
set -euo pipefail

usage() {
  sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}
case "${1:-}" in
  -h|--help) usage 0 ;;
esac

cd "$(git rev-parse --show-toplevel)"
review_sha="$(git rev-parse HEAD)"
echo "review_sha=${review_sha}"

# Rules come only from main. A missing rule file is fatal, with no fallback to the working tree.
rule_file=".claude/agents/deep-reviewer.md"
if git rev-parse -q --verify origin/main >/dev/null 2>&1; then
  if ! git rev-parse -q --verify main >/dev/null 2>&1; then
    echo "ERROR: local main does not exist (origin/main does)" >&2
    exit 1
  fi
  if [ "$(git rev-parse main)" != "$(git rev-parse origin/main)" ]; then
    echo "WARNING: local main ($(git rev-parse --short main)) != origin/main ($(git rev-parse --short origin/main)); rules taken from local main" >&2
    if ! git diff --quiet main origin/main -- "$rule_file"; then
      echo "ERROR: ${rule_file} differs between local main and origin/main; sync local main before reviewing" >&2
      exit 1
    fi
  fi
fi
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
if ! git cat-file -e "main:${rule_file}" 2>/dev/null; then
  echo "ERROR: main:${rule_file} does not exist; refusing to fall back to the working tree" >&2
  exit 1
fi
git show "main:${rule_file}" > "$tmpdir/rules.md"

scope="${1:-}"
if [ -z "$scope" ]; then
  scope="$(git merge-base main HEAD)..HEAD"
  echo "scope(default)=${scope}"
fi

prompt_file="$tmpdir/prompt.md"
cat > "$prompt_file" <<EOF
The rule text below comes from the main branch (git show main:${rule_file}). It is the only rule source for this review. If the working tree copy of ${rule_file} conflicts, the main text wins. Do not read the working tree agent definition.

--- 8< --- main rules begin --- 8< ---
EOF
cat "$tmpdir/rules.md" >> "$prompt_file"
cat >> "$prompt_file" <<EOF
--- >8 --- main rules end --- >8 ---

## Review scope

\`\`\`
${scope}
\`\`\`

## Base sha

Base sha for this review: \`${review_sha}\`. Begin your human-readable conclusion with this line.
Write the full findings to \`reviews/review-${review_sha}.json\` as \`{"review_sha": "${review_sha}", "findings": [...]}\`.
Each finding keeps the rule's fields (severity, file, line, evidence, suggestion, reproduction).
The wrapper adds region, resolved_in_commit and stale.
EOF

echo "prompt: ${prompt_file}"
if ! command -v claude >/dev/null 2>&1; then
  echo "ERROR: claude CLI not available" >&2
  exit 1
fi

out_file="reviews/review-${review_sha}.json"
mkdir -p reviews
# Delete any leftover report first, so a rerun on the same HEAD cannot reuse old findings.
rm -f "$out_file"
claude -p --dangerously-skip-permissions < "$prompt_file"

if [ ! -s "$out_file" ]; then
  echo "ERROR: ${out_file} not generated or empty" >&2
  exit 1
fi
if ! python3 - "$out_file" "$review_sha" "$scope" <<'PYEOF' >/dev/null 2>&1
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
if not isinstance(d, dict) or d.get("review_sha") != sys.argv[2]:
    raise SystemExit(1)
if not isinstance(d.get("findings"), list):
    raise SystemExit(1)
for f in d["findings"]:
    if not isinstance(f, dict):
        raise SystemExit(1)
    for k in ("severity", "file", "line", "evidence", "suggestion"):
        if f.get(k) is None:
            raise SystemExit(1)
d["region"] = sys.argv[3]
d.setdefault("stale", False)
for f in d["findings"]:
    f.setdefault("resolved_in_commit", None)
with open(sys.argv[1], "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
PYEOF
then
  echo "ERROR: ${out_file} validation failed (not JSON / review_sha mismatch / findings malformed)" >&2
  exit 1
fi

# If HEAD moved during the review, the report is stale.
now_sha="$(git rev-parse HEAD)"
if [ "$now_sha" != "$review_sha" ]; then
  echo "STALE: HEAD moved during review (${review_sha} -> ${now_sha})"
  python3 - "$out_file" <<'PYEOF' >/dev/null 2>&1
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
d["stale"] = True
with open(sys.argv[1], "w") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
PYEOF
fi
echo "OK: ${out_file}"
