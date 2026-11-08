#!/usr/bin/env bash
# .claude/hooks/stop-check.sh
# Stop hook: Check ruff + pytest lastfailed + temporary files + uncommitted git changes.
# Non-blocking ("只报不拦"): always exits 0.

set -u

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$PROJECT_DIR" || exit 0

echo "=== [stop-check] Running workspace sanity checks ==="

# 1. Ruff lint check
RUFF_BIN=""
if [ -x "$PROJECT_DIR/.venv/bin/ruff" ]; then
    RUFF_BIN="$PROJECT_DIR/.venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
    RUFF_BIN=$(command -v ruff)
fi

if [ -n "$RUFF_BIN" ]; then
    RUFF_OUT=$("$RUFF_BIN" check . 2>&1)
    RUFF_STATUS=$?
    if [ $RUFF_STATUS -ne 0 ]; then
        echo "[stop-check] ⚠️ Ruff lint warnings:"
        echo "$RUFF_OUT" | head -15
    else
        echo "[stop-check] ✓ Ruff check passed across workspace."
    fi
else
    echo "[stop-check] - Ruff: not installed in .venv or PATH (skipped)."
fi

# 2. Pytest lastfailed check
LASTFAILED_FILE="$PROJECT_DIR/.pytest_cache/v/cache/lastfailed"
if [ -f "$LASTFAILED_FILE" ]; then
    FAIL_COUNT=$(jq 'keys | length' "$LASTFAILED_FILE" 2>/dev/null || echo 0)
    if [ "$FAIL_COUNT" -gt 0 ]; then
        echo "[stop-check] ⚠️ Pytest lastfailed records $FAIL_COUNT failing test(s):"
        jq -r 'keys[]' "$LASTFAILED_FILE" 2>/dev/null | head -10 | sed 's/^/    /'
    else
        echo "[stop-check] ✓ Pytest lastfailed cache is empty."
    fi
else
    echo "[stop-check] ✓ No .pytest_cache lastfailed file found."
fi

# 3. Temporary files check
TEMP_FILES=$(find . -maxdepth 3 -type f \( -name ".DS_Store" -o -name "*~" -o -name "*.swp" -o -name "*.tmp" -o -name "*.bak" \) -not -path "*/.git/*" -not -path "*/node_modules/*" 2>/dev/null | head -20)
if [ -n "$TEMP_FILES" ]; then
    echo "[stop-check] ⚠️ Temporary / untracked cache files detected:"
    echo "$TEMP_FILES" | sed 's/^/    /'
else
    echo "[stop-check] ✓ No temporary editor/OS files detected."
fi

# 4. Uncommitted changes check
GIT_STATUS=$(git status --porcelain 2>/dev/null)
if [ -n "$GIT_STATUS" ]; then
    echo "[stop-check] ℹ️ Uncommitted / untracked git working tree changes:"
    echo "$GIT_STATUS" | head -15 | sed 's/^/    /'
else
    echo "[stop-check] ✓ Working tree is clean."
fi

echo "=== [stop-check] Finished (all checks non-blocking) ==="
exit 0
