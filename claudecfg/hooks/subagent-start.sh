#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ensure_state

label="$(extract_subagent_label)"
scope="$(extract_subagent_scope)"
tmp="$(mktemp)"
jq \
    --arg label "$label" \
    --arg scope "$scope" \
    '.subagent_start_count = ((.subagent_start_count // 0) + 1)
    | .subagents_started = ((.subagents_started + (if ($label | length) > 0 then [$label] else [] end)) | unique)
    | .subagent_instance_count_by_role = (
        (.subagent_instance_count_by_role // {})
        + (if ($label | length) > 0
            then {($label): (((.subagent_instance_count_by_role // {})[$label] // 0) + 1)}
            else {}
           end)
      )
    | .subagent_events = (
        (.subagent_events // [])
        + [(
            {
                index: (.subagent_start_count // 0),
                role: (if ($label | length) > 0 then $label else "" end)
            }
            + (if ($scope | length) > 0 then {purpose: $scope} else {} end)
        )]
      )' "$(state_file)" > "$tmp"
mv "$tmp" "$(state_file)"

if [ -n "$label" ]; then
    emit_context "SubagentStart" "Recorded subagent handoff: @${label}. Parallel same-role handoffs are allowed when they have distinct scopes. Return outcome, changed files or 'no changes', verification status, and remaining risks or next step. If you edit code, run or request verification before stopping."
else
    emit_context "SubagentStart" "Subagent handoff contract: return outcome, changed files or 'no changes', verification status, and remaining risks or next step. If you edit code, run or request verification before stopping."
fi
