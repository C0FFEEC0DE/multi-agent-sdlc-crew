#!/bin/bash

set -euo pipefail

[ $# -eq 1 ] || {
    echo "Usage: $0 COMPARISON_JSON" >&2
    exit 1
}

jq -r '
    def pct($value): (($value * 1000 | round) / 10 | tostring) + "%";
    "## Benchmark Report",
    "",
    "| Metric | Baseline | Candidate | Delta |",
    "| --- | ---: | ---: | ---: |",
    "| Configured tasks | \(.baseline.totals.configured_tasks) | \(.candidate.totals.configured_tasks) | \(.candidate.totals.configured_tasks - .baseline.totals.configured_tasks) |",
    "| Executed tasks | \(.baseline.totals.executed_tasks) | \(.candidate.totals.executed_tasks) | \(.candidate.totals.executed_tasks - .baseline.totals.executed_tasks) |",
    "| Execution coverage | \(pct(.baseline.rates.execution_coverage_rate)) | \(pct(.candidate.rates.execution_coverage_rate)) | \(pct(.candidate.rates.execution_coverage_rate - .baseline.rates.execution_coverage_rate)) |",
    "| Task pass rate | \(pct(.baseline.rates.task_pass_rate)) | \(pct(.candidate.rates.task_pass_rate)) | \(pct(.deltas.task_pass_rate)) |",
    "| Completion rate | \(pct(.baseline.rates.completion_rate)) | \(pct(.candidate.rates.completion_rate)) | \(pct(.deltas.completion_rate)) |",
    "| Verification pass rate | \(pct(.baseline.rates.verification_pass_rate)) | \(pct(.candidate.rates.verification_pass_rate)) | \(pct(.deltas.verification_pass_rate)) |",
    "| Review compliance | \(pct(.baseline.rates.review_compliance_rate)) | \(pct(.candidate.rates.review_compliance_rate)) | \(pct(.deltas.review_compliance_rate)) |",
    "| Docs compliance | \(pct(.baseline.rates.docs_compliance_rate)) | \(pct(.candidate.rates.docs_compliance_rate)) | \(pct(.deltas.docs_compliance_rate)) |",
    "| Policy violations | \(.baseline.totals.policy_violations) | \(.candidate.totals.policy_violations) | \(.deltas.policy_violations) |",
    "| Tool failures | \(.baseline.totals.tool_failures) | \(.candidate.totals.tool_failures) | \(.deltas.tool_failures) |",
    "| Median runtime (s) | \(.baseline.median_runtime_seconds) | \(.candidate.median_runtime_seconds) | \(.deltas.median_runtime_seconds) |",
    "",
    "**Verdict:** `\(.verdict)`",
    (
        if ((.baseline.mode == "mock") or (.candidate.mode == "mock")) then
            "",
            "> Note: at least one side ran in mock mode. Configure `BENCH_RUNNER_CMD` for real agent measurements."
        else empty end
    ),
    (
        if (.reasons | length) > 0 then
            "",
            "**Reasons:**",
            (.reasons[] | "- " + .)
        else empty end
    )
' "$1"
