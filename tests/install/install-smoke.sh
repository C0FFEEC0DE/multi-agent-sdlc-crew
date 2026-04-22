#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_ROOT="$(mktemp -d)"
HOME_DIR="$TMP_ROOT/home"
FIRST_LOG="$TMP_ROOT/install-first.log"
SECOND_LOG="$TMP_ROOT/install-second.log"
BEFORE_MANIFEST="$TMP_ROOT/before.manifest"
AFTER_MANIFEST="$TMP_ROOT/after.manifest"
BACKUP_MANIFEST="$TMP_ROOT/backup.manifest"
BACKUP_DIR=""

cleanup() {
    rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

capture_manifest() {
    local root_dir="$1"
    local tree_root="$2"
    local output_file="$3"

    (
        cd "$root_dir"
        find "$tree_root" -type f -print0 | sort -z | xargs -0 sha256sum
    ) > "$output_file"
}

assert_installed_tree() {
    local root_dir="$1"

    [ -f "$root_dir/.claude/settings.json" ]
    [ -d "$root_dir/.claude/hooks" ]
    [ -d "$root_dir/.claude/commands" ]
    [ -d "$root_dir/.claude/skills" ]
    [ -d "$root_dir/.claude/state" ]
    [ -d "$root_dir/.claude/logs" ]

    while IFS= read -r hook_file; do
        [ -x "$hook_file" ] || {
            echo "Hook not executable: $hook_file" >&2
            exit 1
        }
    done < <(find "$root_dir/.claude/hooks" -type f -name '*.sh' | sort)
}

capture_backup_manifest() {
    local backup_dir="$1"
    local output_file="$2"

    (
        cd "$backup_dir"
        find . -type f -print0 | sort -z | xargs -0 sha256sum | sed 's#  \./#  .claude/#'
    ) > "$output_file"
}

mkdir -p "$HOME_DIR"

( cd "$REPO_ROOT" && HOME="$HOME_DIR" bash ./install.sh ) >"$FIRST_LOG" 2>&1
assert_installed_tree "$HOME_DIR"
capture_manifest "$HOME_DIR" ".claude" "$BEFORE_MANIFEST"

( cd "$REPO_ROOT" && HOME="$HOME_DIR" bash ./claudecfg/install.sh ) >"$SECOND_LOG" 2>&1
assert_installed_tree "$HOME_DIR"
capture_manifest "$HOME_DIR" ".claude" "$AFTER_MANIFEST"

mapfile -t backup_dirs < <(find "$HOME_DIR" -maxdepth 1 -mindepth 1 -type d -name '.claude.backup.*' | sort)
if [ "${#backup_dirs[@]}" -ne 1 ]; then
    echo "Expected exactly one backup directory after reinstall, found ${#backup_dirs[@]}" >&2
    exit 1
fi
BACKUP_DIR="${backup_dirs[0]}"

if [ ! -d "$BACKUP_DIR" ]; then
    echo "Backup directory missing: $BACKUP_DIR" >&2
    exit 1
fi

capture_backup_manifest "$BACKUP_DIR" "$BACKUP_MANIFEST"

cmp -s "$BEFORE_MANIFEST" "$AFTER_MANIFEST"
cmp -s "$BEFORE_MANIFEST" "$BACKUP_MANIFEST"

echo "PASS: installer smoke/idempotency"
