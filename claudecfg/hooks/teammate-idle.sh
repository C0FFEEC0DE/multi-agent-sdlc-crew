#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ensure_state

if reason="$(session_block_reason)"; then
    echo "Do not go idle yet: ${reason}" >&2
    exit 2
fi

if reason="$(session_manager_idle_reason)"; then
    echo "Do not go idle yet: ${reason}" >&2
    exit 2
fi

if reason="$(session_agent_enforcement_reason)"; then
    echo "Do not go idle yet: ${reason}" >&2
    exit 2
fi
