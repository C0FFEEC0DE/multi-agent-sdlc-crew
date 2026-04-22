#!/bin/bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST_FILE="${1:-$REPO_ROOT/tests/hooks/cases.json}"
TMP_ROOT="$(mktemp -d)"
FAILURES=0
TOTAL=0
SCENARIOS=0

# shellcheck disable=SC2329
cleanup() {
    # shellcheck disable=SC2317
    rm -rf "$TMP_ROOT"
}
trap cleanup EXIT

safe_session_id() {
    printf "%s" "$1" | tr -c 'A-Za-z0-9._-' '_'
}

resolve_placeholders() {
    local value="$1"
    local case_tmp="$2"
    local case_home="$3"

    value="${value//__CASE_TMP__/$case_tmp}"
    value="${value//__CASE_HOME__/$case_home}"
    value="${value//__REPO_ROOT__/$REPO_ROOT}"
    printf "%s" "$value"
}

resolve_fs_path() {
    local value="$1"
    local case_tmp="$2"
    local case_home="$3"

    value="$(resolve_placeholders "$value" "$case_tmp" "$case_home")"
    if [ -n "$value" ] && [ "${value#/}" = "$value" ]; then
        value="$REPO_ROOT/$value"
    fi
    printf "%s" "$value"
}

print_failure() {
    local name="$1"
    local message="$2"
    echo "FAIL: $name - $message"
    FAILURES=$((FAILURES + 1))
}

run_case() {
    local case_json="$1"
    local name script_path stdin_path cwd expected_exit stdout_regex stderr_regex stdout_jq state_jq
    local case_tmp case_home stdout_file stderr_file workdir session_id state_seed state_file
    local case_tmp_override case_home_override script_src
    local stdin_src seed_state_src exit_code

    name="$(jq -r '.name' <<<"$case_json")"
    script_path="$(jq -r '.script' <<<"$case_json")"
    stdin_path="$(jq -r '.stdin' <<<"$case_json")"
    cwd="$(jq -r '.cwd // "."' <<<"$case_json")"
    expected_exit="$(jq -r '.expect_exit // 0' <<<"$case_json")"
    stdout_regex="$(jq -r '.stdout_regex // empty' <<<"$case_json")"
    stderr_regex="$(jq -r '.stderr_regex // empty' <<<"$case_json")"
    stdout_jq="$(jq -r '.stdout_jq // empty' <<<"$case_json")"
    state_jq="$(jq -r '.state_jq // empty' <<<"$case_json")"
    state_seed="$(jq -r '.seed_state // empty' <<<"$case_json")"
    case_tmp_override="$(jq -r '.case_tmp // empty' <<<"$case_json")"
    case_home_override="$(jq -r '.case_home // empty' <<<"$case_json")"

    TOTAL=$((TOTAL + 1))
    if [ -n "$case_tmp_override" ]; then
        case_tmp="$case_tmp_override"
    else
        case_tmp="$TMP_ROOT/$name"
    fi
    if [ -n "$case_home_override" ]; then
        case_home="$case_home_override"
    else
        case_home="$case_tmp/home"
    fi
    stdout_file="$case_tmp/stdout"
    stderr_file="$case_tmp/stderr"
    workdir="$(resolve_fs_path "$cwd" "$case_tmp" "$case_home")"
    stdin_src="$(resolve_fs_path "$stdin_path" "$case_tmp" "$case_home")"
    script_src="$(resolve_fs_path "$script_path" "$case_tmp" "$case_home")"

    mkdir -p "$case_home/.claude/state" "$case_tmp"

    if [ ! -f "$stdin_src" ]; then
        print_failure "$name" "stdin fixture not found: $stdin_src"
        return
    fi

    session_id="$(jq -r '.session_id // empty' "$stdin_src")"
    if [ -n "$state_seed" ]; then
        if [ -z "$session_id" ]; then
            print_failure "$name" "seed_state requires session_id in fixture"
            return
        fi
        seed_state_src="$(resolve_fs_path "$state_seed" "$case_tmp" "$case_home")"
        if [ ! -f "$seed_state_src" ]; then
            print_failure "$name" "seed_state fixture not found: $seed_state_src"
            return
        fi
        state_file="$case_home/.claude/state/$(safe_session_id "$session_id").json"
        jq --arg session_id "$session_id" '.session_id = $session_id' "$seed_state_src" > "$state_file"
    fi

    if [ ! -d "$workdir" ]; then
        print_failure "$name" "working directory not found: $workdir"
        return
    fi

    mapfile -t env_pairs < <(jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' <<<"$case_json")
    resolved_env=()
    for pair in "${env_pairs[@]}"; do
        key="${pair%%=*}"
        value="${pair#*=}"
        value="$(resolve_placeholders "$value" "$case_tmp" "$case_home")"
        resolved_env+=("$key=$value")
    done

    set +e
    (
        cd "$workdir"
        env HOME="$case_home" "${resolved_env[@]}" "$script_src" \
            < "$stdin_src" \
            > "$stdout_file" \
            2> "$stderr_file"
    )
    exit_code=$?
    set -e

    if [ "$exit_code" -ne "$expected_exit" ]; then
        print_failure "$name" "expected exit $expected_exit, got $exit_code"
        return
    fi

    if [ -n "$stdout_regex" ] && ! grep -Eq "$stdout_regex" "$stdout_file"; then
        print_failure "$name" "stdout did not match regex: $stdout_regex"
        return
    fi

    if [ -n "$stderr_regex" ] && ! grep -Eq "$stderr_regex" "$stderr_file"; then
        print_failure "$name" "stderr did not match regex: $stderr_regex"
        return
    fi

    if [ -n "$stdout_jq" ] && ! jq -e "$stdout_jq" "$stdout_file" >/dev/null 2>&1; then
        print_failure "$name" "stdout JSON assertion failed: $stdout_jq"
        return
    fi

    if [ -n "$state_jq" ]; then
        if [ -z "$session_id" ]; then
            print_failure "$name" "state assertion requires session_id in fixture"
            return
        fi
        state_file="$case_home/.claude/state/$(safe_session_id "$session_id").json"
        if [ ! -f "$state_file" ]; then
            print_failure "$name" "expected state file not found: $state_file"
            return
        fi
        if ! jq -e "$state_jq" "$state_file" >/dev/null 2>&1; then
            print_failure "$name" "state assertion failed: $state_jq"
            return
        fi
    fi

    while IFS= read -r file_assertion; do
        [ -z "$file_assertion" ] && continue
        file_path="$(jq -r '.path' <<<"$file_assertion")"
        file_regex="$(jq -r '.regex' <<<"$file_assertion")"
        resolved_path="$(resolve_fs_path "$file_path" "$case_tmp" "$case_home")"
        if [ ! -f "$resolved_path" ]; then
            print_failure "$name" "expected file not found: $resolved_path"
            return
        fi
        if ! grep -Eq "$file_regex" "$resolved_path"; then
            print_failure "$name" "file assertion failed for $resolved_path: $file_regex"
            return
        fi
    done < <(jq -c '.file_assertions[]?' <<<"$case_json")

    echo "PASS: $name"
}

run_scenario_step() {
    local scenario_name="$1"
    local scenario_session_id="$2"
    local scenario_tmp="$3"
    local scenario_home="$4"
    local step_json="$5"
    local step_name step_safe_name stdin_path stdin_src step_stdin patched_step_json

    step_name="$(jq -r '.name' <<<"$step_json")"
    stdin_path="$(jq -r '.stdin' <<<"$step_json")"
    stdin_src="$(resolve_fs_path "$stdin_path" "$scenario_tmp" "$scenario_home")"

    if [ ! -f "$stdin_src" ]; then
        print_failure "$scenario_name::$step_name" "stdin fixture not found: $stdin_src"
        return
    fi

    step_safe_name="$(safe_session_id "${scenario_name}__${step_name}")"
    step_stdin="$scenario_tmp/${step_safe_name}.stdin.json"
    jq --arg session_id "$scenario_session_id" '.session_id = $session_id' "$stdin_src" > "$step_stdin"
    patched_step_json="$(jq -c \
        --arg name "$step_safe_name" \
        --arg stdin "$step_stdin" \
        --arg case_tmp "$scenario_tmp" \
        --arg case_home "$scenario_home" \
        '.name = $name | .stdin = $stdin | .case_tmp = $case_tmp | .case_home = $case_home' <<<"$step_json")"

    run_case "$patched_step_json"
}

run_scenario() {
    local scenario_json="$1"
    local name session_id seed_state scenario_tmp scenario_home state_file step_json

    name="$(jq -r '.name' <<<"$scenario_json")"
    session_id="$(jq -r '.session_id // empty' <<<"$scenario_json")"
    if [ -z "$session_id" ]; then
        session_id="$(safe_session_id "$name")"
    fi
    seed_state="$(jq -r '.seed_state // empty' <<<"$scenario_json")"
    scenario_tmp="$TMP_ROOT/$(safe_session_id "$name")"
    scenario_home="$scenario_tmp/home"

    mkdir -p "$scenario_home/.claude/state" "$scenario_tmp"

    if [ -n "$seed_state" ]; then
        seed_state_src="$(resolve_fs_path "$seed_state" "$scenario_tmp" "$scenario_home")"
        if [ ! -f "$seed_state_src" ]; then
            print_failure "$name" "seed_state fixture not found: $seed_state_src"
            return
        fi
        state_file="$scenario_home/.claude/state/$(safe_session_id "$session_id").json"
        jq --arg session_id "$session_id" '.session_id = $session_id' "$seed_state_src" > "$state_file"
    fi

    SCENARIOS=$((SCENARIOS + 1))

    while IFS= read -r step_json; do
        [ -z "$step_json" ] && continue
        run_scenario_step "$name" "$session_id" "$scenario_tmp" "$scenario_home" "$step_json"
    done < <(jq -c '.steps[]' <<<"$scenario_json")
}

manifest_kind() {
    jq -r 'if length == 0 then "cases" elif .[0] | has("steps") then "scenarios" else "cases" end' "$MANIFEST_FILE"
}

MODE="$(manifest_kind)"
if [ "$MODE" = "scenarios" ]; then
    SUITE_TITLE="=== Hook Scenario Tests ==="
else
    SUITE_TITLE="=== Hook Behavior Tests ==="
fi

echo "$SUITE_TITLE"
echo "Manifest: $MANIFEST_FILE"
echo ""

while IFS= read -r entry_json; do
    if [ "$MODE" = "scenarios" ]; then
        run_scenario "$entry_json"
    else
        run_case "$entry_json"
    fi
done < <(jq -c '.[]' "$MANIFEST_FILE")

echo ""
echo "=== Summary ==="
if [ "$MODE" = "scenarios" ]; then
    echo "Scenarios: $SCENARIOS"
    echo "Steps: $TOTAL"
else
    echo "Cases: $TOTAL"
fi
if [ "$FAILURES" -eq 0 ]; then
    if [ "$MODE" = "scenarios" ]; then
        echo "All hook scenario tests passed!"
    else
        echo "All hook behavior tests passed!"
    fi
    exit 0
fi

echo "Failures: $FAILURES"
exit 1
