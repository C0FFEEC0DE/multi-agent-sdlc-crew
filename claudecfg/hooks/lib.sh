#!/bin/bash

set -euo pipefail

HOOK_INPUT="$(cat)"
STATE_ROOT="${HOME}/.claude/state"
LOG_ROOT="${HOME}/.claude/logs"

json_get() {
    local filter="$1"
    jq -r "$filter // empty" <<<"$HOOK_INPUT"
}

json_get_bool() {
    local filter="$1"
    jq -r "if ($filter) == true then \"true\" else \"false\" end" <<<"$HOOK_INPUT"
}

resolve_transcript_path() {
    local path

    path="$(json_get '.transcript_path')"
    if [ -z "$path" ] && [ -f "$(state_file)" ]; then
        path="$(jq -r '.transcript_path // empty' "$(state_file)")"
    fi

    printf "%s" "$path"
}

extract_last_assistant_message_from_transcript() {
    local transcript_path="$1"

    if [ -z "$transcript_path" ] || [ ! -f "$transcript_path" ]; then
        return 0
    fi

    jq -s -r '
        def flattened_text:
            if type == "array" then
                [
                    .[]?
                    | if type == "object" then
                        .text // .result // .content // empty
                    else
                        empty
                    end
                ]
                | map(select(type == "string" and (gsub("\\s+"; " ") | length) > 0))
                | join("\n")
            else
                empty
            end;

        def assistant_text:
            [
                .last_assistant_message?,
                .result?,
                .message?.content? | flattened_text,
                .content? | flattened_text,
                .message?.text?,
                .text?
            ]
            | map(select(type == "string" and (gsub("\\s+"; " ") | length) > 0))
            | .[0] // "";

        [
            reverse[]
            | select(
                (.type? == "assistant")
                or (.type? == "result")
                or (.role? == "assistant")
                or (.message?.role? == "assistant")
            )
            | assistant_text
            | select(length > 0)
        ][0] // ""
    ' "$transcript_path" 2>/dev/null || true
}

resolved_last_assistant_message() {
    local message transcript_path

    message="$(
        jq -r '
            .last_assistant_message
            // .assistant_message
            // .result
            // .message.text
            // .text
            // empty
        ' <<<"$HOOK_INPUT"
    )"
    if [ -n "$message" ]; then
        printf "%s" "$message"
        return 0
    fi

    transcript_path="$(resolve_transcript_path)"
    extract_last_assistant_message_from_transcript "$transcript_path"
}

timestamp_utc() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

safe_session_id() {
    local raw
    raw="$(json_get '.session_id')"
    if [ -z "$raw" ]; then
        raw="no-session"
    fi
    printf "%s" "$raw" | tr -c 'A-Za-z0-9._-' '_'
}

state_file() {
    printf "%s/%s.json" "$STATE_ROOT" "$(safe_session_id)"
}

ensure_dirs() {
    mkdir -p "$STATE_ROOT" "$LOG_ROOT"
}

ensure_state() {
    local file
    file="$(state_file)"
    ensure_dirs
    if [ -f "$file" ]; then
        return
    fi

    jq -n \
        --arg session_id "$(json_get '.session_id')" \
        --arg cwd "$(json_get '.cwd')" \
        --arg transcript_path "$(json_get '.transcript_path')" \
        --arg created_at "$(timestamp_utc)" \
        '{
            session_id: $session_id,
            cwd: $cwd,
            transcript_path: $transcript_path,
            created_at: $created_at,
            task_type: "other",
            edited: false,
            code_changed: false,
            docs_changed: false,
            tests_ok: false,
            tests_failed: false,
            lint_ok: false,
            lint_failed: false,
            build_ok: false,
            build_failed: false,
            detected_test_command: "",
            detected_lint_command: "",
            detected_build_command: "",
            last_test_command: "",
            last_lint_command: "",
            last_build_command: "",
            subagent_start_count: 0,
            subagents_started: [],
            required_subagents: [],
            required_subagent_any_of: [],
            stop_block_count: 0,
            stop_block_reason: "",
            stop_block_message: "",
            subagent_stop_block_count: 0,
            subagent_stop_block_reason: "",
            subagent_stop_block_message: "",
            files: []
        }' > "$file"
}

update_state() {
    local jq_program="$1"
    local file
    local tmp

    file="$(state_file)"
    tmp="$(mktemp)"
    jq "$jq_program" "$file" > "$tmp"
    mv "$tmp" "$file"
}

record_loop_block() {
    local prefix="$1"
    local reason="$2"
    local message="$3"
    local count_key reason_key message_key file tmp previous_reason previous_message previous_count next_count

    case "$prefix" in
        stop)
            count_key="stop_block_count"
            reason_key="stop_block_reason"
            message_key="stop_block_message"
            ;;
        subagent_stop)
            count_key="subagent_stop_block_count"
            reason_key="subagent_stop_block_reason"
            message_key="subagent_stop_block_message"
            ;;
        *)
            return 1
            ;;
    esac

    file="$(state_file)"
    previous_reason="$(jq -r --arg key "$reason_key" '.[$key] // empty' "$file")"
    previous_message="$(jq -r --arg key "$message_key" '.[$key] // empty' "$file")"
    previous_count="$(jq -r --arg key "$count_key" '.[$key] // 0' "$file")"

    if [ "$previous_reason" = "$reason" ] && [ "$previous_message" = "$message" ]; then
        next_count=$((previous_count + 1))
    else
        next_count=1
    fi

    tmp="$(mktemp)"
    jq \
        --arg count_key "$count_key" \
        --arg reason_key "$reason_key" \
        --arg message_key "$message_key" \
        --arg reason "$reason" \
        --arg message "$message" \
        --argjson count "$next_count" \
        '.[$count_key] = $count
        | .[$reason_key] = $reason
        | .[$message_key] = $message' "$file" > "$tmp"
    mv "$tmp" "$file"
}

clear_loop_block() {
    local prefix="$1"
    local count_key reason_key message_key tmp

    case "$prefix" in
        stop)
            count_key="stop_block_count"
            reason_key="stop_block_reason"
            message_key="stop_block_message"
            ;;
        subagent_stop)
            count_key="subagent_stop_block_count"
            reason_key="subagent_stop_block_reason"
            message_key="subagent_stop_block_message"
            ;;
        *)
            return 1
            ;;
    esac

    tmp="$(mktemp)"
    jq \
        --arg count_key "$count_key" \
        --arg reason_key "$reason_key" \
        --arg message_key "$message_key" \
        '.[$count_key] = 0
        | .[$reason_key] = ""
        | .[$message_key] = ""' "$(state_file)" > "$tmp"
    mv "$tmp" "$(state_file)"
}

loop_block_count() {
    local prefix="$1"
    local key

    case "$prefix" in
        stop)
            key="stop_block_count"
            ;;
        subagent_stop)
            key="subagent_stop_block_count"
            ;;
        *)
            return 1
            ;;
    esac

    jq -r --arg key "$key" '.[$key] // 0' "$(state_file)"
}

emit_loop_aware_block() {
    local prefix="$1"
    local reason="$2"
    local message="$3"
    local count final_reason

    record_loop_block "$prefix" "$reason" "$message"
    count="$(loop_block_count "$prefix")"
    final_reason="$reason"

    if [ "$count" -ge 3 ]; then
        final_reason="Repeated stop-block loop detected (${count}x): ${reason} Do not retry the same final response again; change the summary or perform the required action first."
    fi

    jq -n --arg reason "$final_reason" '{
        decision: "block",
        reason: $reason
    }'
}

append_jsonl() {
    local name="$1"
    local payload="$2"
    ensure_dirs
    printf "%s\n" "$payload" >> "${LOG_ROOT}/${name}"
}

emit_context() {
    local event_name="$1"
    local message="$2"
    jq -n \
        --arg event_name "$event_name" \
        --arg message "$message" \
        '{
            hookSpecificOutput: {
                hookEventName: $event_name,
                additionalContext: $message
            }
        }'
}

emit_pretool_decision() {
    local decision="$1"
    local reason="$2"
    jq -n \
        --arg decision "$decision" \
        --arg reason "$reason" \
        '{
            hookSpecificOutput: {
                hookEventName: "PreToolUse",
                permissionDecision: $decision,
                permissionDecisionReason: $reason
            }
        }'
}

emit_permission_request_deny() {
    local message="$1"
    jq -n \
        --arg message "$message" \
        '{
            hookSpecificOutput: {
                hookEventName: "PermissionRequest",
                decision: {
                    behavior: "deny",
                    message: $message
                }
            }
        }'
}

stop_safe_no_change_footer_hint() {
    printf ' If this reply did not introduce additional changes, still report the actual verification, review, changed files, and remaining risks instead of using a no-change shortcut after code or config changes.'
}

message_has_line_prefix() {
    local message="$1"
    local prefix="$2"
    local line=""

    while IFS= read -r line; do
        if [[ "$line" == "$prefix"* ]]; then
            return 0
        fi
    done <<<"$message"

    return 1
}

extract_subagent_label() {
    local raw

    raw="$(
        jq -r '
        .agent_alias
        // .agentAlias
        // .alias
        // .subagent_alias
        // .subagentAlias
        // .subagent_type
        // .subagentType
        // .tool_input.agent_alias
        // .tool_input.agentAlias
        // .tool_input.alias
        // .tool_input.subagent_alias
        // .tool_input.subagentAlias
        // .tool_input.subagent_type
        // .tool_input.subagentType
        // .agent_name
        // .agentName
        // .subagent_name
        // .subagentName
        // .name
        // .tool_input.agent
        // .tool_input.agent_name
        // .tool_input.agentName
        // .tool_input.subagent_name
        // .tool_input.subagentName
        // .tool_input.name
        // .tool_input.type
        // .tool_input.agent_type
        // .tool_input.agentType
        // .agent_type
        // .agentType
        // .type
        // empty
    ' <<<"$HOOK_INPUT"
    )"

    canonicalize_subagent_label "$raw"
}

canonicalize_subagent_label() {
    local raw="$1"
    local normalized

    normalized="$(printf "%s" "$raw" \
        | tr '[:upper:]' '[:lower:]' \
        | sed -E 's/^@//; s/[[:space:]_]+/-/g; s/[^a-z0-9.-]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')"

    case "$normalized" in
        "")
            printf ""
            ;;
        a|architect|the-architect)
            printf "a"
            ;;
        e|explorer|nerd)
            printf "e"
            ;;
        bug|bugbuster|bug-pattern-hunter|bug-pattern)
            printf "bug"
            ;;
        dbg|debugger|debugging-specialist)
            printf "dbg"
            ;;
        t|tester|paranoid)
            printf "t"
            ;;
        cr|code-reviewer|code-review|reviewer|toxic-senior)
            printf "cr"
            ;;
        doc|docwriter|wiki-wiki|documentation-writer|docs-writer)
            printf "doc"
            ;;
        hk|housekeeper|the-cleaner|cleaner)
            printf "hk"
            ;;
        m|manager|big-boss)
            printf "m"
            ;;
        *)
            printf "%s" "$normalized"
            ;;
    esac
}

array_contains() {
    local needle="$1"
    shift

    local item
    for item in "$@"; do
        if [ "$item" = "$needle" ]; then
            return 0
        fi
    done

    return 1
}

format_subagent_list() {
    local item result=""

    for item in "$@"; do
        if [ -n "$result" ]; then
            result="${result}, "
        fi
        result="${result}@${item}"
    done

    printf "%s" "${result:-none}"
}

format_subagent_group() {
    local item result=""

    for item in "$@"; do
        if [ -n "$result" ]; then
            result="${result}/"
        fi
        result="${result}@${item}"
    done

    printf "%s" "$result"
}

detect_node_script() {
    local script_name="$1"
    if [ -f package.json ] && jq -e --arg name "$script_name" '.scripts[$name] != null' package.json >/dev/null 2>&1; then
        printf "npm run %s" "$script_name"
        return 0
    fi
    return 1
}

detect_test_cmd() {
    local cmd=""

    if cmd="$(detect_node_script test)"; then
        printf "%s" "$cmd"
        return 0
    fi
    if [ -f Cargo.toml ]; then
        printf "cargo test"
        return 0
    fi
    if [ -f go.mod ]; then
        printf "go test ./..."
        return 0
    fi
    if [ -f pytest.ini ] || [ -f pyproject.toml ] || [ -d tests ]; then
        printf "pytest"
        return 0
    fi

    return 1
}

detect_lint_cmd() {
    local cmd=""

    if cmd="$(detect_node_script lint)"; then
        printf "%s" "$cmd"
        return 0
    fi
    if [ -f Cargo.toml ]; then
        printf "cargo clippy --all-targets --all-features -- -D warnings"
        return 0
    fi
    if [ -f pyproject.toml ] || [ -d tests ]; then
        printf "python -m compileall ."
        return 0
    fi

    return 1
}

detect_build_cmd() {
    local cmd=""

    if cmd="$(detect_node_script build)"; then
        printf "%s" "$cmd"
        return 0
    fi
    if [ -f Cargo.toml ]; then
        printf "cargo build"
        return 0
    fi
    if [ -f go.mod ]; then
        printf "go build ./..."
        return 0
    fi
    if [ -f Makefile ] || [ -f makefile ]; then
        printf "make"
        return 0
    fi

    return 1
}

command_class() {
    local command="$1"

    case "$command" in
        *"pytest"*|*"npm test"*|*"npm run test"*|*"pnpm test"*|*"yarn test"*|*"cargo test"*|*"go test"*|*"ctest"*|*"make test"*)
            printf "test"
            ;;
        *"npm run lint"*|*"pnpm lint"*|*"yarn lint"*|*"ruff"*|*"flake8"*|*"cargo clippy"*|*"golangci-lint"*|*"eslint"*|*"shellcheck"*|*"python -m compileall "*|*"make lint"*)
            printf "lint"
            ;;
        *"npm run build"*|*"pnpm build"*|*"yarn build"*|*"cargo build"*|*"go build"*|*"cmake --build"*|*"make"*)
            printf "build"
            ;;
        *)
            printf "other"
            ;;
    esac
}

is_release_or_deploy_command() {
    local command="$1"

    [[ "$command" == *"npm publish"* \
        || "$command" == *"cargo publish"* \
        || "$command" == *"docker push"* \
        || "$command" == *"gh release"* \
        || "$command" == *"kubectl apply"* \
        || "$command" == *"helm upgrade"* ]]
}

is_remote_shell_bootstrap_command() {
    local command="$1"

    if { [[ "$command" =~ (^|[[:space:]])curl($|[[:space:]]) ]] || [[ "$command" =~ (^|[[:space:]])wget($|[[:space:]]) ]]; } \
        && [[ "$command" =~ [|][[:space:]]*[[:alnum:]_./-]*(sh|bash|zsh|dash|ksh)($|[[:space:]]) ]]; then
        return 0
    fi

    return 1
}

message_mentions_verification_status() {
    local message="$1"

    message_has_line_prefix "$message" "Verification status:" \
        || message_has_line_prefix "$message" "Verification:" \
        || message_has_line_prefix "$message" "Verification result:" \
        || message_has_line_prefix "$message" "Test status:" \
        || message_has_line_prefix "$message" "Tests:"
}

message_mentions_review_outcome() {
    local message="$1"

    message_has_line_prefix "$message" "Review outcome:" \
        || message_has_line_prefix "$message" "Review status:" \
        || message_has_line_prefix "$message" "Review:"
}

message_mentions_changed_files() {
    local message="$1"

    message_has_line_prefix "$message" "Changed files:" \
        || message_has_line_prefix "$message" "Key files changed:" \
        || message_has_line_prefix "$message" "Files changed:" \
        || message_has_line_prefix "$message" "Updated files:" \
        || message_has_line_prefix "$message" "Modified files:" \
        || message_has_line_prefix "$message" "No files changed:"
}

message_mentions_remaining_risks() {
    local message="$1"

    message_has_line_prefix "$message" "Remaining risks:" \
        || message_has_line_prefix "$message" "Residual risks:" \
        || message_has_line_prefix "$message" "Risks:"
}

message_mentions_next_step() {
    local message="$1"

    grep -Eiq '(next step|next steps|next:|follow-up|follow up|pending next|следующ(ий|ие) шаг|дальше:|следующее:)' <<<"$message"
}

message_mentions_concrete_outcome() {
    local message="$1"

    grep -Eiq '(outcome|result|implemented|updated|fixed|investigated|reviewed|documented|added|removed|refactored|changed|created|no changes|completed|done|исправил|обновил|добавил|удалил|проверил|нашел|сделал|без изменений)' <<<"$message"
}

message_reports_no_changes() {
    local message="$1"

    message_has_line_prefix "$message" "No changes were made." \
        || message_has_line_prefix "$message" "No files changed." \
        || message_has_line_prefix "$message" "Nothing changed."
}

session_block_reason() {
    local state code_changed tests_ok tests_failed lint_ok lint_failed build_ok build_failed
    local detected_test_command detected_lint_command detected_build_command
    local last_test_command last_lint_command last_build_command
    local has_detected_verification="false"
    local has_successful_verification="false"

    state="$(state_file)"
    code_changed="$(jq -r '.code_changed // false' "$state")"
    tests_ok="$(jq -r '.tests_ok // false' "$state")"
    tests_failed="$(jq -r '.tests_failed // false' "$state")"
    lint_ok="$(jq -r '.lint_ok // false' "$state")"
    lint_failed="$(jq -r '.lint_failed // false' "$state")"
    build_ok="$(jq -r '.build_ok // false' "$state")"
    build_failed="$(jq -r '.build_failed // false' "$state")"
    detected_test_command="$(jq -r '.detected_test_command // empty' "$state")"
    detected_lint_command="$(jq -r '.detected_lint_command // empty' "$state")"
    detected_build_command="$(jq -r '.detected_build_command // empty' "$state")"
    last_test_command="$(jq -r '.last_test_command // empty' "$state")"
    last_lint_command="$(jq -r '.last_lint_command // empty' "$state")"
    last_build_command="$(jq -r '.last_build_command // empty' "$state")"

    if [ -n "$detected_test_command" ] || [ -n "$detected_lint_command" ] || [ -n "$detected_build_command" ]; then
        has_detected_verification="true"
    fi

    if [ "$tests_ok" = "true" ] || [ "$lint_ok" = "true" ] || [ "$build_ok" = "true" ]; then
        has_successful_verification="true"
    fi

    if [ "$code_changed" = "true" ] && [ "$tests_failed" = "true" ]; then
        printf "Code or config changed, but the latest test command failed in this session (%s). Fix the failure and rerun verification before stopping." "${last_test_command:-test command}"
        return 0
    fi

    if [ "$code_changed" = "true" ] && [ "$lint_failed" = "true" ]; then
        printf "Code or config changed, but the latest lint/static-check command failed in this session (%s). Fix the failure and rerun it successfully before stopping." "${last_lint_command:-lint command}"
        return 0
    fi

    if [ "$code_changed" = "true" ] && [ "$build_failed" = "true" ]; then
        printf "Code or config changed, but the latest build command failed in this session (%s). Fix the failure and rerun it successfully before stopping." "${last_build_command:-build command}"
        return 0
    fi

    if [ "$code_changed" = "true" ] && [ "$has_detected_verification" = "true" ] && [ "$has_successful_verification" != "true" ]; then
        printf "Code or config changed, but no successful verification command was recorded in this session. Run a detected test, lint, or build command before stopping."
        return 0
    fi

    return 1
}

session_agent_enforcement_reason() {
    local state task_type started_json group_json group_label missing_groups_text satisfied alias
    local -a started=() required=() group=() missing=() missing_groups=()

    state="$(state_file)"
    task_type="$(jq -r '.task_type // "other"' "$state")"

    mapfile -t started < <(jq -r '.subagents_started[]? // empty' "$state")
    mapfile -t required < <(jq -r '.required_subagents[]? // empty' "$state")

    while IFS= read -r group_json; do
        [ -z "$group_json" ] && continue
        mapfile -t group < <(jq -r '.[]? // empty' <<<"$group_json")
        [ "${#group[@]}" -eq 0 ] && continue

        satisfied="false"
        for alias in "${group[@]}"; do
            if array_contains "$alias" "${started[@]}"; then
                satisfied="true"
                break
            fi
        done
        if [ "$satisfied" != "true" ]; then
            group_label="$(format_subagent_group "${group[@]}")"
            missing_groups+=("$group_label")
        fi
    done < <(jq -c '.required_subagent_any_of[]? // empty' "$state")

    if [ "${#required[@]}" -eq 0 ] && [ "${#missing_groups[@]}" -eq 0 ]; then
        return 1
    fi

    for alias in "${required[@]}"; do
        if ! array_contains "$alias" "${started[@]}"; then
            missing+=("$alias")
        fi
    done

    if [ "${#missing[@]}" -eq 0 ] && [ "${#missing_groups[@]}" -eq 0 ]; then
        return 1
    fi

    started_json="$(format_subagent_list "${started[@]}")"
    printf "Agent-enforced workflow requires specific subagent handoffs before completion for %s work." "$task_type"
    if [ "${#missing[@]}" -gt 0 ]; then
        printf " Missing required roles: %s." "$(format_subagent_list "${missing[@]}")"
    fi
    if [ "${#missing_groups[@]}" -gt 0 ]; then
        missing_groups_text="$(printf "%s\n" "${missing_groups[@]}" | paste -sd ',' - | sed 's/,/, /g')"
        printf " Missing one-of groups: %s." "$missing_groups_text"
    fi
    printf " Used so far: %s." "$started_json"
    return 0

    return 1
}

is_docs_path() {
    local file_path="$1"

    case "$file_path" in
        *.md|*.mdx|*.txt|*.rst|*.adoc|*.markdown|*/docs/*|README*|CHANGELOG*|CLAUDE.md)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}
