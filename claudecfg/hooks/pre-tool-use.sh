#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

command="$(json_get '.tool_input.command' | tr '[:upper:]' '[:lower:]')"

if [[ "$command" =~ (^|[[:space:]])sudo($|[[:space:]]) ]]; then
    emit_pretool_decision "deny" "sudo is blocked by the SDLC safety profile."
    exit 0
fi

if [[ "$command" =~ (^|[[:space:]])mkfs(\.[^[:space:]]+)?($|[[:space:]]) ]] || [[ "$command" =~ (^|[[:space:]])dd($|[[:space:]]) ]]; then
    emit_pretool_decision "deny" "Dangerous disk commands are blocked."
    exit 0
fi

if [[ "$command" == *"rm -rf /"* ]] \
    || { [[ "$command" =~ git[[:space:]]+push ]] && [[ "$command" =~ (^|[[:space:]])(-f|--force|--force-with-lease)($|[[:space:]]) ]]; }; then
    emit_pretool_decision "deny" "Destructive commands are blocked by policy."
    exit 0
fi

if [[ "$command" == *"rm -rf ~"* || "$command" == *"rm -rf $HOME"* || "$command" == *"rm -rf ."* ]]; then
    emit_pretool_decision "deny" "Recursive deletion of home or current directory is blocked."
    exit 0
fi

if [[ "$command" == *"git reset --hard"* ]]; then
    emit_pretool_decision "deny" "Destructive commands are blocked by policy."
    exit 0
fi

if is_release_or_deploy_command "$command"; then
    emit_pretool_decision "deny" "release/deploy actions are intentionally out of scope for this workflow profile."
    exit 0
fi

if is_remote_shell_bootstrap_command "$command"; then
    emit_pretool_decision "deny" "Piping remote scripts into the shell is blocked."
    exit 0
fi

emit_pretool_decision "allow" "Command is allowed by the SDLC safety profile."
exit 0
