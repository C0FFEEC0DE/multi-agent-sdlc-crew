#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ensure_state

command="$(json_get '.tool_input.command')"
error="$(json_get '.error')"
class="$(command_class "$command")"

case "$class" in
    test)
        _atomic_state_update \
            --arg command "$command" \
            '.tests_failed = true
            | .tests_ok = false
            | .last_test_command = $command'
        emit_context "PostToolUseFailure" "Verification command failed: ${command}. Fix the failure before marking the task done. Error: ${error}"
        ;;
    lint)
        _atomic_state_update \
            --arg command "$command" \
            '.lint_failed = true
            | .lint_ok = false
            | .last_lint_command = $command'
        emit_context "PostToolUseFailure" "Lint/static-check command failed: ${command}. Resolve the issue before stopping. Error: ${error}"
        ;;
    build)
        _atomic_state_update \
            --arg command "$command" \
            '.build_failed = true
            | .build_ok = false
            | .last_build_command = $command'
        emit_context "PostToolUseFailure" "Build command failed: ${command}. Fix the build or explicitly explain why it is not required. Error: ${error}"
        ;;
    *)
        exit 0
        ;;
esac
