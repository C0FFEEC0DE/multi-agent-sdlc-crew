#!/bin/bash

set -euo pipefail

[ $# -eq 1 ] || {
    echo "Usage: $0 SUMMARY_JSON" >&2
    exit 1
}

summary_file="$1"
max_recovered_tasks="${BENCH_MAX_RECOVERED_TASKS:-}"
max_summary_repaired="${BENCH_MAX_SUMMARY_REPAIRED_TASKS:-}"

# Debug output for GitHub Actions
if [ -f "$summary_file" ]; then
    echo "Checking summary file: $summary_file"
    echo "File contents:"
    cat "$summary_file" >&2 || echo "(cannot read file)" >&2
else
    echo "ERROR: Summary file not found: $summary_file" >&2
    exit 1
fi

gate_expr='
    .totals.configured_tasks > 0
    and .totals.executed_tasks > 0
    and .totals.executed_tasks == .totals.configured_tasks
    and .totals.tasks == .totals.executed_tasks
    and .totals.passed == .totals.tasks
    and .totals.tool_failures == 0
    and .totals.policy_violations == 0
    and ((.totals.unresolved_tasks // 0) == 0)
'

if [ -n "$max_recovered_tasks" ]; then
    gate_expr="$gate_expr and .totals.recovered_tasks <= \$max_recovered_tasks"
fi

if [ -n "$max_summary_repaired" ]; then
    gate_expr="$gate_expr and .totals.summary_repaired <= \$max_summary_repaired"
fi

if ! jq -e "$gate_expr" \
    --argjson max_recovered_tasks "${max_recovered_tasks:-0}" \
    --argjson max_summary_repaired "${max_summary_repaired:-0}" \
    "$summary_file" >/dev/null 2>&1; then
    echo "ERROR: Benchmark summary failed gate check!" >&2
    echo "Summary contents:"
    cat "$summary_file" >&2
    exit 1
fi
