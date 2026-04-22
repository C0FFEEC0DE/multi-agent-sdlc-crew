#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR=""
TASK_GLOB="bench/tasks/subagents/smoke/*.json"
TASK_LIST_FILE=""
TASK_LABEL=""
MODE="${BENCH_MODE:-}"
SOURCE_REF="${BENCH_SOURCE_REF:-working-tree}"
FAIL_FAST="${BENCH_FAIL_FAST:-0}"
PROJECT_CLAUDE_DIR="${BENCH_CLAUDE_PROFILE_DIR:-}"
configured_task_count=0
executed_task_count=0

relative_task_path() {
    local path="$1"
    case "$path" in
        "$REPO_ROOT"/*)
            printf '%s\n' "${path#"$REPO_ROOT"/}"
            ;;
        *)
            printf '%s\n' "$path"
            ;;
    esac
}

json_array_from_items() {
    if [ "$#" -eq 0 ]; then
        printf '[]'
        return
    fi
    printf '%s\n' "$@" | jq -R . | jq -s .
}

usage() {
    echo "Usage: $0 --output-dir DIR [--task-glob GLOB | --task-list-file FILE] [--task-label LABEL] [--mode mock|command] [--ref REF]" >&2
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --task-glob)
            TASK_GLOB="$2"
            shift 2
            ;;
        --task-list-file)
            TASK_LIST_FILE="$2"
            shift 2
            ;;
        --task-label)
            TASK_LABEL="$2"
            shift 2
            ;;
        --mode)
            MODE="$2"
            shift 2
            ;;
        --ref)
            SOURCE_REF="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

[ -n "$OUTPUT_DIR" ] || usage

if [ -z "$PROJECT_CLAUDE_DIR" ]; then
    if [ -d "$HOME/.claude" ]; then
        PROJECT_CLAUDE_DIR="$HOME/.claude"
    else
        PROJECT_CLAUDE_DIR="${REPO_ROOT}/.claude"
    fi
fi

mkdir -p "$HOME/.claude" "$HOME/.claude/state" "$HOME/.claude/logs"

if [ -n "$TASK_LIST_FILE" ] && [ -n "$TASK_GLOB" ] && [ "$TASK_GLOB" != "bench/tasks/subagents/smoke/*.json" ]; then
    usage
fi

if [ -z "$MODE" ]; then
    if [ -n "${BENCH_RUNNER_CMD:-}" ]; then
        MODE="command"
    else
        MODE="mock"
    fi
fi

case "$MODE" in
    mock)
        RUNNER_CMD="$REPO_ROOT/scripts/mock-benchmark-runner.sh"
        RUNNER_DESCRIPTION="mock-benchmark-runner"
        ;;
    command)
        : "${BENCH_RUNNER_CMD:?BENCH_RUNNER_CMD is required in command mode}"
        RUNNER_CMD="$BENCH_RUNNER_CMD"
        RUNNER_DESCRIPTION="$BENCH_RUNNER_CMD"
        ;;
    *)
        echo "Unsupported benchmark mode: $MODE" >&2
        exit 1
        ;;
esac

mkdir -p "$OUTPUT_DIR/tasks"

shopt -s nullglob
if [ -n "$TASK_LIST_FILE" ]; then
    if [ ! -f "$TASK_LIST_FILE" ]; then
        echo "Task list file does not exist: $TASK_LIST_FILE" >&2
        exit 1
    fi
    mapfile -t task_files < <(
        sed '/^[[:space:]]*$/d' "$TASK_LIST_FILE" \
        | while IFS= read -r task_path; do
            case "$task_path" in
                /*) printf '%s\n' "$task_path" ;;
                *) printf '%s\n' "$REPO_ROOT/$task_path" ;;
            esac
          done
    )
else
    mapfile -t task_files < <(compgen -G "$REPO_ROOT/$TASK_GLOB" || true)
fi
shopt -u nullglob
configured_task_count="${#task_files[@]}"

if [ "${#task_files[@]}" -eq 0 ]; then
    if [ -n "$TASK_LIST_FILE" ]; then
        echo "No benchmark tasks matched task list file: $TASK_LIST_FILE" >&2
    else
        echo "No benchmark tasks matched glob: $TASK_GLOB" >&2
    fi
    exit 1
fi

if [ -z "$TASK_LABEL" ]; then
    if [ -n "$TASK_LIST_FILE" ]; then
        TASK_LABEL="task-list:$(basename "$TASK_LIST_FILE")"
    else
        TASK_LABEL="$TASK_GLOB"
    fi
fi

result_files=()
selected_task_paths=()
selected_task_ids=()
executed_task_paths=()
executed_task_ids=()
failed_task_paths=()
failed_task_ids=()
for task_file in "${task_files[@]}"; do
    selected_task_paths+=("$(relative_task_path "$task_file")")
    selected_task_ids+=("$(jq -r '.id' "$task_file")")
done

for task_file in "${task_files[@]}"; do
    task_id="$(jq -r '.id' "$task_file")"
    task_path_rel="$(relative_task_path "$task_file")"
    category="$(jq -r '.category' "$task_file")"
    fixture_name="$(jq -r '.fixture' "$task_file")"
    fixture_dir="$REPO_ROOT/bench/fixtures/$fixture_name"
    task_output_dir="$OUTPUT_DIR/tasks/$task_id"
    task_workdir="$task_output_dir/workdir"

    if [ ! -d "$fixture_dir" ]; then
        echo "Missing benchmark fixture directory: $fixture_dir" >&2
        exit 1
    fi

    rm -rf "$task_output_dir"
    mkdir -p "$task_workdir"
    cp -R "$fixture_dir"/. "$task_workdir"/
    if [ -d "$PROJECT_CLAUDE_DIR" ]; then
        mkdir -p "$task_workdir/.claude"
        cp -R "$PROJECT_CLAUDE_DIR"/. "$task_workdir/.claude"/
    fi

    export BENCH_TASK_FILE="$task_file"
    export BENCH_TASK_ID="$task_id"
    export BENCH_OUTPUT_DIR="$task_output_dir"
    export BENCH_WORKDIR="$task_workdir"
    export BENCH_FIXTURE_DIR="$fixture_dir"
    export BENCH_REPO_ROOT="$REPO_ROOT"

    echo "=== Benchmark task: $task_id ==="
    echo "Runner: $RUNNER_DESCRIPTION"
    echo "Category: $category"
    echo "Fixture: $fixture_name"
    echo "Task file: $task_file"
    echo "Workdir: $task_workdir"
    echo "Model: ${OLLAMA_MODEL:-<unset>}"
    echo "Max output tokens: ${CLAUDE_CODE_MAX_OUTPUT_TOKENS:-<unset>}"

    if [ "$MODE" = "mock" ]; then
        "$RUNNER_CMD"
    else
        bash -lc "$RUNNER_CMD"
    fi

    if [ ! -f "$task_output_dir/result.json" ]; then
        echo "Benchmark runner did not produce result.json for task: $task_id" >&2
        exit 1
    fi

    if ! jq -e '
        .task_id and .status and has("completed") and has("verification_required") and has("tests_run")
        and has("tests_passed") and has("review_required") and has("review_present")
        and has("docs_required") and has("docs_updated")
        and has("policy_violations") and has("tool_failures")
        and has("runtime_seconds") and .notes
    ' "$task_output_dir/result.json" >/dev/null; then
        echo "Benchmark result has missing required fields: $task_output_dir/result.json" >&2
        exit 1
    fi

    result_files+=("$task_output_dir/result.json")
    executed_task_count=$((executed_task_count + 1))
    executed_task_paths+=("$task_path_rel")
    executed_task_ids+=("$task_id")

    task_failed=0
    if jq -e '.status != "passed"' "$task_output_dir/result.json" >/dev/null; then
        failed_task_paths+=("$task_path_rel")
        failed_task_ids+=("$task_id")
        task_failed=1
    fi

    if [ -f "$task_output_dir/task-summary.txt" ]; then
        cat "$task_output_dir/task-summary.txt"
    else
        jq -r '
            "Status: \(.status)",
            "Changed files: \((.changed_files // []) | join(", "))",
            "Notes: \(.notes)"
        ' "$task_output_dir/result.json"
    fi
    echo "Structured result:"
    cat "$task_output_dir/result.json"

    if [ "$task_failed" = "1" ] && { [ "$FAIL_FAST" = "1" ] || [ "$FAIL_FAST" = "true" ]; }; then
        echo "Fail-fast enabled; stopping benchmark after first failing task: $task_id"
        break
    fi
done

unexecuted_task_paths=()
unexecuted_task_ids=()
for ((index=executed_task_count; index<configured_task_count; index++)); do
    unexecuted_task_paths+=("${selected_task_paths[$index]}")
    unexecuted_task_ids+=("${selected_task_ids[$index]}")
done

unresolved_task_paths=("${failed_task_paths[@]}" "${unexecuted_task_paths[@]}")
unresolved_task_ids=("${failed_task_ids[@]}" "${unexecuted_task_ids[@]}")

selected_task_paths_json="$(json_array_from_items "${selected_task_paths[@]}")"
selected_task_ids_json="$(json_array_from_items "${selected_task_ids[@]}")"
executed_task_paths_json="$(json_array_from_items "${executed_task_paths[@]}")"
executed_task_ids_json="$(json_array_from_items "${executed_task_ids[@]}")"
unexecuted_task_paths_json="$(json_array_from_items "${unexecuted_task_paths[@]}")"
unexecuted_task_ids_json="$(json_array_from_items "${unexecuted_task_ids[@]}")"
unresolved_task_paths_json="$(json_array_from_items "${unresolved_task_paths[@]}")"
unresolved_task_ids_json="$(json_array_from_items "${unresolved_task_ids[@]}")"

source_sha="$(git rev-parse --short HEAD)"
generated_at="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

jq -s \
    --arg schema_version "1.0" \
    --arg mode "$MODE" \
    --arg runner "$RUNNER_DESCRIPTION" \
    --arg generated_at "$generated_at" \
    --arg source_ref "$SOURCE_REF" \
    --arg source_sha "$source_sha" \
    --arg task_glob "$TASK_LABEL" \
    --argjson configured_tasks "$configured_task_count" \
    --argjson executed_tasks "$executed_task_count" \
    --argjson selected_task_paths "$selected_task_paths_json" \
    --argjson selected_task_ids "$selected_task_ids_json" \
    --argjson executed_task_paths "$executed_task_paths_json" \
    --argjson executed_task_ids "$executed_task_ids_json" \
    --argjson unexecuted_task_paths "$unexecuted_task_paths_json" \
    --argjson unexecuted_task_ids "$unexecuted_task_ids_json" \
    --argjson unresolved_task_paths "$unresolved_task_paths_json" \
    --argjson unresolved_task_ids "$unresolved_task_ids_json" \
    '
    def rate($num; $den):
        if $den == 0 then 0 else ($num / $den) end;
    def median($arr):
        ($arr | sort) as $sorted
        | if ($sorted | length) == 0 then 0
          elif ($sorted | length) % 2 == 1 then $sorted[($sorted | length / 2 | floor)]
          else (($sorted[($sorted | length / 2 | floor) - 1] + $sorted[($sorted | length / 2 | floor)]) / 2)
          end;
    . as $tasks
    | ($tasks | length) as $total
    | {
        schema_version: $schema_version,
        mode: $mode,
        runner: $runner,
        generated_at: $generated_at,
        source_ref: $source_ref,
        source_sha: $source_sha,
        task_glob: $task_glob,
        selected_task_paths: $selected_task_paths,
        selected_task_ids: $selected_task_ids,
        executed_task_paths: $executed_task_paths,
        executed_task_ids: $executed_task_ids,
        unexecuted_task_paths: $unexecuted_task_paths,
        unexecuted_task_ids: $unexecuted_task_ids,
        unresolved_task_paths: $unresolved_task_paths,
        unresolved_task_ids: $unresolved_task_ids,
        totals: {
            configured_tasks: $configured_tasks,
            selected_tasks: ($selected_task_paths | length),
            executed_tasks: $executed_tasks,
            tasks: $executed_tasks,
            unexecuted_tasks: ($unexecuted_task_paths | length),
            unresolved_tasks: ($unresolved_task_paths | length),
            passed: ($tasks | map(select(.status == "passed")) | length),
            clean_passed: ($tasks | map(select(.status == "passed" and (.recovered_nonzero_exit != true) and ((.summary_repaired_by // "none") == "none"))) | length),
            completed: ($tasks | map(select(.completed == true)) | length),
            verification_required: ($tasks | map(select(.verification_required == true)) | length),
            tests_run: ($tasks | map(select(.tests_run == true)) | length),
            tests_passed: ($tasks | map(select(.tests_passed == true)) | length),
            review_required: ($tasks | map(select(.review_required == true)) | length),
            review_present: ($tasks | map(select(.review_present == true)) | length),
            docs_required: ($tasks | map(select(.docs_required == true)) | length),
            docs_updated: ($tasks | map(select(.docs_updated == true)) | length),
            recovered_tasks: ($tasks | map(select(.recovered_nonzero_exit == true)) | length),
            timeout_recovered: ($tasks | map(select(.timeout_recovered == true)) | length),
            max_turns_recovered: ($tasks | map(select(.max_turns_recovered == true)) | length),
            summary_repaired: ($tasks | map(select((.summary_repaired_by // "none") != "none")) | length),
            policy_violations: ($tasks | map(.policy_violations) | add),
            tool_failures: ($tasks | map(.tool_failures) | add)
        },
        rates: {
            task_pass_rate: rate(($tasks | map(select(.status == "passed")) | length); $total),
            clean_pass_rate: rate(($tasks | map(select(.status == "passed" and (.recovered_nonzero_exit != true) and ((.summary_repaired_by // "none") == "none"))) | length); $total),
            completion_rate: rate(($tasks | map(select(.completed == true)) | length); $total),
            verification_rate: rate(($tasks | map(select((.verification_required == false) or (.tests_run == true))) | length); $total),
            verification_pass_rate: rate(($tasks | map(select((.verification_required == false) or (.tests_passed == true))) | length); $total),
            review_compliance_rate: rate(($tasks | map(select((.review_required == false) or (.review_present == true))) | length); $total),
            docs_compliance_rate: rate(($tasks | map(select((.docs_required == false) or (.docs_updated == true))) | length); $total),
            recovered_task_rate: rate(($tasks | map(select(.recovered_nonzero_exit == true)) | length); $total),
            summary_repair_rate: rate(($tasks | map(select((.summary_repaired_by // "none") != "none")) | length); $total),
            execution_coverage_rate: rate($executed_tasks; $configured_tasks),
            unexecuted_rate: rate(($unexecuted_task_paths | length); ($selected_task_paths | length)),
            unresolved_rate: rate(($unresolved_task_paths | length); ($selected_task_paths | length))
        },
        median_runtime_seconds: median($tasks | map(.runtime_seconds)),
        tasks: $tasks
    }
    ' "${result_files[@]}" > "$OUTPUT_DIR/summary.json"

echo "Benchmark summary written to $OUTPUT_DIR/summary.json"
benchmark_report_path="$OUTPUT_DIR/benchmark-report.md"
bash "$REPO_ROOT/scripts/render-benchmark-summary.sh" "$OUTPUT_DIR/summary.json" > "$benchmark_report_path"
echo "Benchmark markdown report written to $benchmark_report_path"
cat "$benchmark_report_path"
jq -r '
    "Benchmark totals:",
    "- configured tasks: \(.totals.configured_tasks)",
    "- executed tasks: \(.totals.executed_tasks)",
    "- execution coverage: \(.rates.execution_coverage_rate)",
    "- unexecuted tasks: \(.totals.unexecuted_tasks)",
    "- unresolved tasks: \(.totals.unresolved_tasks)",
    "- tasks: \(.totals.tasks)",
    "- passed: \(.totals.passed)",
    "- clean_passed: \(.totals.clean_passed)",
    "- recovered_tasks: \(.totals.recovered_tasks)",
    "- summary_repaired: \(.totals.summary_repaired)",
    "- tool_failures: \(.totals.tool_failures)",
    "- task_pass_rate: \(.rates.task_pass_rate)",
    "- clean_pass_rate: \(.rates.clean_pass_rate)",
    "- recovered_task_rate: \(.rates.recovered_task_rate)",
    "- summary_repair_rate: \(.rates.summary_repair_rate)"
' "$OUTPUT_DIR/summary.json"
