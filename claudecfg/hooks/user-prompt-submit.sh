#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/lib.sh"

ensure_state

stop_safe_hint=" If a later reply in the same session makes no additional changes, still report the actual verification, review, changed files, and remaining risks instead of using a no-change shortcut after code or config changes."

prompt="$(json_get '.prompt' | tr '[:upper:]' '[:lower:]')"
task_type="other"
required_subagents='[]'
required_subagent_any_of='[]'
context_message=""

if grep -Eiq '(bug|fix|defect|баг|ошиб|исправ)' <<<"$prompt"; then
    task_type="bugfix"
elif grep -Eiq '(refactor|rename|cleanup|tech debt|рефактор|почист|переимен)' <<<"$prompt"; then
    task_type="refactor"
elif grep -Eiq '(feature|implement|add support|integrat|new capability|фич|добав|интеграц|подключ|модел|pyrit|openrouter)' <<<"$prompt"; then
    task_type="feature"
elif grep -Eiq '(review|audit|ревью|аудит|проверь)' <<<"$prompt"; then
    task_type="review"
elif grep -Eiq '(docs|readme|document|док|ридми)' <<<"$prompt"; then
    task_type="docs"
fi

case "$task_type" in
    feature)
        required_subagents='["t","cr"]'
        required_subagent_any_of='[["e","a"]]'
        context_message="Treat this as a feature workflow. Required subagent handoffs before completion: @t, @cr, and one of @e/@a. Finish implementation, run verification successfully, address review findings, and update docs when behavior changes. release/deploy remains out of scope.${stop_safe_hint}"
        ;;
    bugfix)
        required_subagents='["t","cr"]'
        required_subagent_any_of='[["bug","e","dbg"]]'
        context_message="Treat this as a bugfix workflow. Required subagent handoffs before completion: @t, @cr, and one of @bug/@e/@dbg. Reproduce or describe the failure mode, implement the fix, execute regression verification, and update docs if behavior changed.${stop_safe_hint}"
        ;;
    refactor)
        required_subagents='["t","cr"]'
        required_subagent_any_of='[["a","e","hk"]]'
        context_message="Treat this as a refactor workflow. Required subagent handoffs before completion: @t, @cr, and one of @a/@e/@hk. Keep scope to structure and maintainability, preserve behavior, run verification after changes, and summarize risks plus changed files before stopping.${stop_safe_hint}"
        ;;
    review)
        required_subagents='["cr"]'
        required_subagent_any_of='[]'
        context_message="Treat this as a review workflow. Required subagent handoff before completion: @cr. Focus on findings first, call out residual risks or testing gaps, and keep implementation out of scope unless the user explicitly asks for fixes.${stop_safe_hint}"
        ;;
    docs)
        required_subagents='["doc"]'
        required_subagent_any_of='[]'
        context_message="Treat this as a docs workflow. Required subagent handoff before completion: @doc. Keep documentation accurate to current behavior, include examples when they materially help, and note any remaining drift or missing verification.${stop_safe_hint}"
        ;;
esac

tmp="$(mktemp)"
jq \
    --arg task_type "$task_type" \
    --argjson required_subagents "$required_subagents" \
    --argjson required_subagent_any_of "$required_subagent_any_of" \
    '.task_type = $task_type
    | .required_subagents = $required_subagents
    | .required_subagent_any_of = $required_subagent_any_of' "$(state_file)" > "$tmp"
mv "$tmp" "$(state_file)"

if [ -n "$context_message" ]; then
    emit_context "UserPromptSubmit" "$context_message"
    exit 0
fi

exit 0
