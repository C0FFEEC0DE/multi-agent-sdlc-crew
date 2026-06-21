#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

payload="$(jq -n \
    --arg ts "$(timestamp_utc)" \
    --arg session_id "$(json_get '.session_id')" \
    --arg trigger "$(json_get '.trigger')" \
    --arg compact_summary "$(json_get '.compact_summary')" \
    '{
        ts: $ts,
        session_id: $session_id,
        trigger: $trigger,
        compact_summary: $compact_summary
    }')"

append_jsonl "post-compact.jsonl" "$payload"

# Re-inject the durable progress ledger after a compaction so the agent keeps
# its place. The ledger is plain markdown the controller appends to during
# Subagent-Driven Development (one line per completed task). The primary
# recovery mechanism is the agent reading the file at skill start; this
# best-effort injection re-surfaces it in the freshly compacted context. When
# no ledger exists the hook emits nothing, preserving prior behavior.
ledger_file="$(progress_ledger_path 2>/dev/null || true)"
if [ -n "$ledger_file" ] && [ -f "$ledger_file" ]; then
    ledger_content="$(cat "$ledger_file" 2>/dev/null || true)"
    if [ -n "$(printf '%s' "$ledger_content" | tr -d '[:space:]')" ]; then
        emit_context "PostCompact" "$(printf 'You are resuming after a context compaction. Your durable progress ledger follows — trust it and git log over your own recollection; tasks it marks complete are DONE, do not re-dispatch them.\n\n%s' "$ledger_content")"
    fi
fi