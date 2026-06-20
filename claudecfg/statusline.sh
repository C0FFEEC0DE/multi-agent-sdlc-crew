#!/bin/bash
# Token-aware Claude Code status line.
#
# Claude Code pipes a JSON session object to stdin on every status refresh:
#   { "model": { "display_name": "..." }, "workspace": { "current_dir": "..." },
#     "session_id": "...", "version": "...", "output_style": { "name": "..." } }
# We print one line: cwd basename | model | output style. Kept deliberately
# short so the status line never competes with the prompt for attention.

set -euo pipefail

input="$(cat 2>/dev/null || true)"

model=""
cwd=""
style=""

if [ -n "$input" ] && command -v jq >/dev/null 2>&1; then
    model="$(printf '%s' "$input" | jq -r '.model.display_name // .model.id // empty' 2>/dev/null || true)"
    cwd="$(printf '%s' "$input" | jq -r '.workspace.current_dir // .cwd // empty' 2>/dev/null || true)"
    style="$(printf '%s' "$input" | jq -r '.output_style.name // empty' 2>/dev/null || true)"
fi

[ -z "$cwd" ] && cwd="${PWD}"
dir_name="$(basename "$cwd")"

parts=()
[ -n "$dir_name" ] && parts+=("$dir_name")
[ -n "$model" ] && parts+=("$model")
[ -n "$style" ] && [ "$style" != "Default" ] && parts+=("$style")

# Join with " | "; fall back to a minimal label if nothing parsed.
if [ "${#parts[@]}" -gt 0 ]; then
    out=""
    for p in "${parts[@]}"; do
        if [ -n "$out" ]; then out="$out | $p"; else out="$p"; fi
    done
    printf '%s' "$out"
else
    printf 'claude'
fi