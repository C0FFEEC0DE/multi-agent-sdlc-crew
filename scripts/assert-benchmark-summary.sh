#!/bin/bash

set -euo pipefail

[ $# -eq 1 ] || {
    echo "Usage: $0 SUMMARY_JSON" >&2
    exit 1
}

summary_file="$1"

jq -e '
    .totals.configured_tasks > 0
    and .totals.executed_tasks > 0
    and .totals.executed_tasks <= .totals.configured_tasks
    and .totals.tasks == .totals.executed_tasks
    and .totals.passed == .totals.tasks
    and .totals.tool_failures == 0
    and .totals.policy_violations == 0
' "$summary_file" >/dev/null
