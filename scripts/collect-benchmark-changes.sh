#!/bin/bash

set -euo pipefail

EVENT_NAME=""
OUTPUT_FILE=""
BASE_REF="main"
LOOKBACK_HOURS="24"
REF_NAME=""

usage() {
    echo "Usage: $0 --event EVENT --output FILE [--base-ref REF] [--lookback-hours HOURS] [--ref-name REF]" >&2
    exit 1
}

while [ $# -gt 0 ]; do
    case "$1" in
        --event)
            EVENT_NAME="$2"
            shift 2
            ;;
        --output)
            OUTPUT_FILE="$2"
            shift 2
            ;;
        --base-ref)
            BASE_REF="$2"
            shift 2
            ;;
        --lookback-hours)
            LOOKBACK_HOURS="$2"
            shift 2
            ;;
        --ref-name)
            REF_NAME="$2"
            shift 2
            ;;
        *)
            usage
            ;;
    esac
done

[ -n "$EVENT_NAME" ] || usage
[ -n "$OUTPUT_FILE" ] || usage

mkdir -p "$(dirname "$OUTPUT_FILE")"
: > "$OUTPUT_FILE"

case "$EVENT_NAME" in
    pull_request)
        git fetch --no-tags --prune --depth=1 origin "$BASE_REF"
        git diff --name-only "origin/$BASE_REF...HEAD" | sed '/^$/d' | sort -u > "$OUTPUT_FILE"
        ;;
    schedule)
        git fetch --no-tags --prune --depth=1 origin main
        git log --since="${LOOKBACK_HOURS} hours ago" --name-only --pretty=format: origin/main \
            | sed '/^$/d' | sort -u > "$OUTPUT_FILE"
        ;;
    workflow_dispatch)
        git fetch --no-tags --prune --depth=1 origin "$BASE_REF"
        if [ -n "$REF_NAME" ] && [ "$REF_NAME" != "$BASE_REF" ]; then
            git diff --name-only "origin/$BASE_REF...HEAD" | sed '/^$/d' | sort -u > "$OUTPUT_FILE"
        else
            git log --since="${LOOKBACK_HOURS} hours ago" --name-only --pretty=format: HEAD \
                | sed '/^$/d' | sort -u > "$OUTPUT_FILE"
        fi
        ;;
    *)
        echo "Unsupported event for benchmark change collection: $EVENT_NAME" >&2
        exit 1
        ;;
esac

printf 'Collected %s changed files for %s\n' "$(wc -l < "$OUTPUT_FILE" | tr -d ' ')" "$EVENT_NAME"

# Debug: output file contents if not empty
if [ -s "$OUTPUT_FILE" ]; then
    echo "Changed files:"
    cat "$OUTPUT_FILE" >&2
else
    echo "WARNING: No changed files collected for $EVENT_NAME" >&2
fi
