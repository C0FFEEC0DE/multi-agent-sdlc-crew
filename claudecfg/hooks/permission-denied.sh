#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

command="$(json_get '.tool_input.command' | tr '[:upper:]' '[:lower:]')"

if command_is_hard_denied_by_profile "$command"; then
    emit_permission_denied_no_retry
    exit 0
fi

if ! permission_denied_should_retry; then
    emit_permission_denied_no_retry
    exit 0
fi

emit_permission_denied_retry
