#!/usr/bin/env node
// hook-dispatcher.mjs — single entry point for every hook event.
//
// Reads stdin as a Buffer, parses one JSON object, routes to a pure event
// handler, writes exactly one JSON object to stdout, and sends diagnostics
// only to stderr. Node standard library only: no child_process.exec, no
// shell:true, no interpolated command strings.
//
// Phase 1 ships the I/O contract and routing only. Event handlers return a
// neutral passthrough until Phase 2 ports the real workflow/policy/summary
// behavior, so the installed plugin is inert but safe.
import { pathToFileURL } from 'node:url';
import { parseHookInput, readStdin } from './hook-input.mjs';
import { additionalContext, passthrough, serialize, terminalCancel } from './hook-output.mjs';
import { resolveDataRoot, resolveSessionId } from './util.mjs';
import { statePaths, appendEvent } from './state.mjs';
import { classifyPrompt, userPromptResetPatch } from './workflow.mjs';

// UserPromptSubmit: classify the prompt, persist the task type / manager mode /
// required roles / docs flag plus the stop-loop reset to session state, and
// emit the workflow context message (if any) as additionalContext. Mirrors
// claudecfg/hooks/user-prompt-submit.sh.
function handleUserPromptSubmit(parsed) {
  const prompt = parsed.data?.prompt ?? '';
  const cls = classifyPrompt(prompt);
  const sid = resolveSessionId(parsed.sessionId);
  const paths = statePaths(resolveDataRoot(), sid);
  const fields = {
    session_id: parsed.sessionId ?? '',
    cwd: parsed.cwd ?? '',
    transcript_path: parsed.transcriptPath ?? '',
    task_type: cls.taskType,
    manager_mode: cls.managerMode,
    docs_required: cls.docsRequired,
    required_subagents: cls.requiredSubagents,
    required_subagent_any_of: cls.requiredSubagentAnyOf,
    ...userPromptResetPatch(),
  };
  try { appendEvent(paths, 'set_many', { fields }); } catch (e) {
    // State write failure must not block the prompt; report to stderr only.
    process.stderr.write(`hook-dispatcher: state write failed: ${e?.message ?? e}\n`);
  }
  if (cls.contextMessage) return additionalContext(cls.contextMessage, 'UserPromptSubmit');
  return passthrough();
}

// Event handlers. Each takes the parsed input and returns a JSON-serializable
// output object (or null/undefined for passthrough). Handlers not yet ported
// return a neutral passthrough so the installed plugin stays inert but safe.
const handlers = {
  SessionStart: () => passthrough(),
  InstructionsLoaded: () => passthrough(),
  UserPromptSubmit: handleUserPromptSubmit,
  PreToolUse: () => passthrough(),
  PermissionRequest: () => passthrough(),
  PermissionDenied: () => passthrough(),
  PostToolUse: () => passthrough(),
  PostToolUseFailure: () => passthrough(),
  SubagentStart: () => passthrough(),
  SubagentStop: () => passthrough(),
  Stop: () => passthrough(),
  TeammateIdle: () => passthrough(),
  TaskCompleted: () => passthrough(),
  Notification: () => passthrough(),
  ConfigChange: () => passthrough(),
  PreCompact: () => passthrough(),
  PostCompact: () => passthrough(),
  SessionEnd: () => passthrough(),
};

/**
 * Pure, side-effect-free dispatch core. Given an event name and a parsed
 * input, return the output object. A handler crash or an unknown event never
 * blocks the runtime — it degrades to passthrough.
 */
export function dispatch(event, parsed) {
  const fn = handlers[event];
  if (typeof fn !== 'function') return passthrough();
  try {
    return fn(parsed) ?? passthrough();
  } catch {
    // Never block or stop the runtime on a handler bug; degrade to passthrough.
    return passthrough();
  }
}

/** Extract the --event argument from argv. */
export function eventFromArgs(argv) {
  const i = argv.indexOf('--event');
  return i >= 0 && argv[i + 1] ? argv[i + 1] : null;
}

async function main() {
  const argEvent = eventFromArgs(process.argv.slice(2));
  const buf = await readStdin();
  const parsed = parseHookInput(buf);

  if (parsed.error) {
    process.stderr.write(`hook-dispatcher: input warning: ${parsed.error}\n`);
  }

  // --event takes precedence; fall back to hook_event_name in stdin.
  const event = argEvent || parsed.event;
  if (!event) {
    process.stderr.write('hook-dispatcher: no event (missing --event and hook_event_name)\n');
  }

  const out = dispatch(event, parsed);
  process.stdout.write(serialize(out));
}

// Run only when invoked directly (not when imported by tests).
const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;
if (isMain) {
  main().catch((err) => {
    // A fatal crash must never fail the hook runtime. Emit a terminal
    // diagnostic to stderr and exit 0 so Claude Code is not blocked.
    process.stderr.write(`hook-dispatcher fatal: ${err?.message ?? err}\n`);
    process.stdout.write(serialize(terminalCancel(`hook dispatcher fatal error`)));
    process.exit(0);
  });
}