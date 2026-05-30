#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ensure_state

test_cmd=""
lint_cmd=""
build_cmd=""

if detected="$(detect_test_cmd)"; then
    test_cmd="$detected"
fi
if detected="$(detect_lint_cmd)"; then
    lint_cmd="$detected"
fi
if detected="$(detect_build_cmd)"; then
    build_cmd="$detected"
fi

_atomic_state_update \
    --arg test_cmd "$test_cmd" \
    --arg lint_cmd "$lint_cmd" \
    --arg build_cmd "$build_cmd" \
    '.detected_test_command = $test_cmd
    | .detected_lint_command = $lint_cmd
    | .detected_build_command = $build_cmd'

if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
    {
        echo "export CLAUDE_SDLC_PROFILE=hook-gated"
        echo "export CLAUDE_RELEASE_AUTOMATION=disabled"
        echo "export CLAUDE_SESSION_STATE_FILE=\"$(state_file)\""
        [ -n "$test_cmd" ] && echo "export PROJECT_TEST_CMD=\"$test_cmd\""
        [ -n "$lint_cmd" ] && echo "export PROJECT_LINT_CMD=\"$lint_cmd\""
        [ -n "$build_cmd" ] && echo "export PROJECT_BUILD_CMD=\"$build_cmd\""
    } >> "$CLAUDE_ENV_FILE"
fi

message="Hook-gated SDLC is active. Required flow: discover -> design -> implement -> verify -> review -> docs when behavior changes -> cleanup. release/deploy automation is intentionally disabled in this profile."
if [ -n "$test_cmd" ] || [ -n "$lint_cmd" ] || [ -n "$build_cmd" ]; then
    message="${message} Detected commands:"
    [ -n "$test_cmd" ] && message="${message} test=${test_cmd};"
    [ -n "$lint_cmd" ] && message="${message} lint=${lint_cmd};"
    [ -n "$build_cmd" ] && message="${message} build=${build_cmd};"
fi

emit_context "SessionStart" "$message"
