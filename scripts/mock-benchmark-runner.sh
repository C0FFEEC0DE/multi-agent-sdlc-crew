#!/bin/bash

set -euo pipefail

: "${BENCH_TASK_FILE:?BENCH_TASK_FILE is required}"
: "${BENCH_OUTPUT_DIR:?BENCH_OUTPUT_DIR is required}"

task_id="$(jq -r '.id' "$BENCH_TASK_FILE")"
task_path="$BENCH_TASK_FILE"
if [ -n "${BENCH_REPO_ROOT:-}" ]; then
    case "$BENCH_TASK_FILE" in
        "$BENCH_REPO_ROOT"/*)
            task_path="${BENCH_TASK_FILE#"$BENCH_REPO_ROOT"/}"
            ;;
    esac
fi
category="$(jq -r '.category' "$BENCH_TASK_FILE")"
review_required="$(jq -r '.review_required' "$BENCH_TASK_FILE")"
docs_required="$(jq -r '.docs_required' "$BENCH_TASK_FILE")"
verification_required="$(jq -r '.verification_required' "$BENCH_TASK_FILE")"

case "$category" in
    bugfix) runtime_seconds=18 ;;
    feature) runtime_seconds=26 ;;
    refactor) runtime_seconds=20 ;;
    docs) runtime_seconds=8 ;;
    *) runtime_seconds=15 ;;
esac

mkdir -p "$BENCH_OUTPUT_DIR"

jq -n \
    --arg task_id "$task_id" \
    --arg task_path "$task_path" \
    --arg status "passed" \
    --arg notes "Mock runner produced a synthetic passing result. Configure BENCH_RUNNER_CMD for real agent evaluation." \
    --argjson completed true \
    --argjson verification_required "$verification_required" \
    --argjson tests_run "$verification_required" \
    --argjson tests_passed "$verification_required" \
    --argjson review_required "$review_required" \
    --argjson review_present "$review_required" \
    --argjson docs_required "$docs_required" \
    --argjson docs_updated "$docs_required" \
    --argjson policy_violations 0 \
    --argjson tool_failures 0 \
    --argjson runtime_seconds "$runtime_seconds" \
    '{
        task_id: $task_id,
        task_path: $task_path,
        status: $status,
        completed: $completed,
        verification_required: $verification_required,
        tests_run: $tests_run,
        tests_passed: $tests_passed,
        review_required: $review_required,
        review_present: $review_present,
        docs_required: $docs_required,
        docs_updated: $docs_updated,
        policy_violations: $policy_violations,
        tool_failures: $tool_failures,
        runtime_seconds: $runtime_seconds,
        notes: $notes
    }' > "$BENCH_OUTPUT_DIR/result.json"
