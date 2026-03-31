#!/bin/bash

set -euo pipefail

[ $# -eq 1 ] || {
    echo "Usage: $0 SUMMARY_JSON" >&2
    exit 1
}

summary_file="$1"
max_recovered_tasks="${BENCH_MAX_RECOVERED_TASKS:-}"
max_summary_repaired="${BENCH_MAX_SUMMARY_REPAIRED_TASKS:-}"

gate_expr='
    .totals.configured_tasks > 0
    and .totals.executed_tasks > 0
    and .totals.executed_tasks <= .totals.configured_tasks
    and .totals.tasks == .totals.executed_tasks
    and .totals.passed == .totals.tasks
    and .totals.tool_failures == 0
    and .totals.policy_violations == 0
'

if [ -n "$max_recovered_tasks" ]; then
    gate_expr="$gate_expr and .totals.recovered_tasks <= \$max_recovered_tasks"
fi

if [ -n "$max_summary_repaired" ]; then
    gate_expr="$gate_expr and .totals.summary_repaired <= \$max_summary_repaired"
fi

jq -e "$gate_expr" \
    --argjson max_recovered_tasks "${max_recovered_tasks:-0}" \
    --argjson max_summary_repaired "${max_summary_repaired:-0}" \
    "$summary_file" >/dev/null
