#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

# emit_context variant for potentially large messages (e.g. the progress
# ledger): writes the message to a temp file and passes it to jq via --rawfile
# instead of --arg. A >32KiB --arg value can exceed the OS command-line length
# limit (Windows CreateProcess ~32KiB), so the ledger is injected through a
# file. jq --rawfile reads the file content as a raw string and JSON-encodes it,
# so the JSON output is byte-identical to emit_context for the same message.
emit_context_rawfile() {
    local event_name="$1" message="$2" msgfile
    msgfile="$(mktemp 2>/dev/null || mktemp -t cc-emit 2>/dev/null || echo "/tmp/cc-emit-$$.tmp")"
    printf '%s' "$message" > "$msgfile"
    jq -n \
        --arg event_name "$event_name" \
        --rawfile message "$msgfile" \
        '{
            hookSpecificOutput: {
                hookEventName: $event_name,
                additionalContext: $message
            }
        }'
    rm -f "$msgfile"
}

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
LEDGER_MAX_BYTES="${CLAUDE_CREW_LEDGER_MAX_BYTES:-65536}"
case "$LEDGER_MAX_BYTES" in
    ''|*[!0-9]*)
        LEDGER_MAX_BYTES=65536
        ;;
esac

ledger_file="$(progress_ledger_path 2>/dev/null || true)"
if [ -n "$ledger_file" ] && [ -f "$ledger_file" ]; then
    ledger_size=0
    if stat -c%s "$ledger_file" >/dev/null 2>&1; then
        ledger_size="$(stat -c%s "$ledger_file" 2>/dev/null || echo 0)"
    else
        ledger_size="$(stat -f%z "$ledger_file" 2>/dev/null || echo 0)"
    fi

    truncation_note=""
    if [ "${ledger_size:-0}" -gt "$LEDGER_MAX_BYTES" ]; then
        # head -c truncates at byte boundaries, which can split a multi-byte
        # UTF-8 sequence. Sanitize with iconv when available so jq --arg does
        # not receive invalid UTF-8; fall back to the raw bytes if iconv is
        # absent. Progress-ledger lines are normally ASCII task markers.
        ledger_content="$(head -c "$LEDGER_MAX_BYTES" "$ledger_file" 2>/dev/null \
            | { iconv -c -f UTF-8 -t UTF-8 2>/dev/null || cat; })"
        truncation_note="[Ledger truncated: ${ledger_size} bytes exceeds ${LEDGER_MAX_BYTES} byte limit. Verify recent tasks manually.]"
    else
        ledger_content="$(cat "$ledger_file" 2>/dev/null || true)"
    fi

    if [ -n "$(printf '%s' "$ledger_content" | tr -d '[:space:]')" ]; then
        ledger_prefix='You are resuming after a context compaction. Your durable progress ledger follows — trust it and git log over your own recollection; tasks it marks complete are DONE, do not re-dispatch them.\n\n'
        if [ -n "$truncation_note" ]; then
            emit_context_rawfile "PostCompact" "$(printf '%s%s\n\n%s' "$ledger_prefix" "$ledger_content" "$truncation_note")"
        else
            emit_context_rawfile "PostCompact" "$(printf '%s%s' "$ledger_prefix" "$ledger_content")"
        fi
    fi
fi