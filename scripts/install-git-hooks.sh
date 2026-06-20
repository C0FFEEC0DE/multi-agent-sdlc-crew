#!/bin/bash
# Installs the optional local git hooks (a pre-push secret scan) into the
# current repository's .git/hooks. Opt-in and repo-local — it does NOT touch
# your global git config or ~/.claude.
#
# Usage:  bash scripts/install-git-hooks.sh
# Remove: rm .git/hooks/pre-push

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC="${SCRIPT_DIR}/git-hooks/pre-push"
DEST_DIR="$(git rev-parse --git-path hooks)"

if [ ! -f "$SRC" ]; then
    echo "ERROR: source hook not found at $SRC" >&2
    exit 1
fi

mkdir -p "$DEST_DIR"
cp "$SRC" "$DEST_DIR/pre-push"
chmod +x "$DEST_DIR/pre-push"
echo "Installed pre-push secret-scan hook -> ${DEST_DIR}/pre-push"
echo "To remove: rm ${DEST_DIR}/pre-push"