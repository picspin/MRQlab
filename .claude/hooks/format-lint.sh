#!/usr/bin/env bash
# .claude/hooks/format-lint.sh
# PostToolUse hook: Run ruff check on edited .py files.
# Non-blocking ("只提示不拦编辑"): always exits 0.

set -u

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$PWD}"
FILE_PATH="${1:-}"

# If file path was not passed as an argument, safely parse from PostToolUse stdin JSON via jq
if [ -z "$FILE_PATH" ]; then
    if [ ! -t 0 ]; then
        FILE_PATH=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty' 2>/dev/null || true)
    fi
fi

# Exit cleanly if no file path resolved
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Only lint Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Resolve file relative to project directory if needed
TARGET="$FILE_PATH"
if [ ! -f "$TARGET" ] && [ -f "$PROJECT_DIR/$FILE_PATH" ]; then
    TARGET="$PROJECT_DIR/$FILE_PATH"
fi

if [ ! -f "$TARGET" ]; then
    exit 0
fi

# Locate ruff in .venv or system PATH
RUFF_BIN=""
if [ -x "$PROJECT_DIR/.venv/bin/ruff" ]; then
    RUFF_BIN="$PROJECT_DIR/.venv/bin/ruff"
elif command -v ruff >/dev/null 2>&1; then
    RUFF_BIN=$(command -v ruff)
fi

if [ -z "$RUFF_BIN" ]; then
    echo "[format-lint] Notice: ruff not found in .venv or PATH; skipped lint check for $FILE_PATH"
    exit 0
fi

# Run ruff check (warn only, never block)
RUFF_OUTPUT=$("$RUFF_BIN" check "$TARGET" 2>&1)
RUFF_STATUS=$?

if [ $RUFF_STATUS -ne 0 ]; then
    echo "[format-lint] ⚠️ Ruff lint issues detected in $FILE_PATH (non-blocking):" >&2
    echo "$RUFF_OUTPUT" >&2
else
    echo "[format-lint] ✓ Ruff check passed for $FILE_PATH"
fi

# Crucial constraint: always exit 0 ("只提示不拦编辑")
exit 0
