#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
: "${PYTHON:=python}"
out="${1:-/private/tmp/mrqlab-ismrm-checks}"
mkdir -p "$out"
"$PYTHON" -m pytest tests/ -q > "$out/pytest.txt" 2>&1
(cd apps/web && npm test) > "$out/web.txt" 2>&1
(cd apps/web && npx --no-install tsc --noEmit) > "$out/tsc.txt" 2>&1
"$PYTHON" docs/ismrm/reproduce.py "$out/verticals" > "$out/verticals.txt" 2>&1
cat "$out/pytest.txt" "$out/web.txt" "$out/tsc.txt"
