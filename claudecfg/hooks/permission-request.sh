#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

command="$(json_get '.tool_input.command' | tr '[:upper:]' '[:lower:]')"

if [[ "$command" =~ (^|[[:space:]])sudo($|[[:space:]]) ]]; then
    emit_permission_request_deny "sudo is blocked by this profile"
    exit 0
fi

if [[ "$command" =~ (^|[[:space:]])mkfs(\.[^[:space:]]+)?($|[[:space:]]) ]] || [[ "$command" =~ (^|[[:space:]])dd($|[[:space:]]) ]]; then
    emit_permission_request_deny "dangerous disk commands are blocked by this profile"
    exit 0
fi

if is_dangerous_rm_command "$command" || [[ "$command" == *"git reset --hard"* ]] || is_force_push_command "$command"; then
    emit_permission_request_deny "destructive commands are blocked by this profile"
    exit 0
fi

if is_release_or_deploy_command "$command"; then
    emit_permission_request_deny "release/deploy requests are outside this profile"
    exit 0
fi

if is_remote_shell_bootstrap_command "$command"; then
    emit_permission_request_deny "remote shell bootstrap commands require manual review outside the hook flow"
    exit 0
fi
