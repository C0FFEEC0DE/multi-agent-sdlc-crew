// Node port of tests/test_settings_hooks.py — validates claudecfg/settings.json
// hook structure per the official Claude Code hooks documentation.
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const REPO = join(import.meta.dirname, '..', '..');
const SETTINGS_PATH = join(REPO, 'claudecfg', 'settings.json');

const HOOK_EVENTS = new Set([
  'SessionStart', 'InstructionsLoaded', 'UserPromptSubmit', 'PreToolUse',
  'PermissionRequest', 'PermissionDenied', 'PostToolUse', 'PostToolUseFailure',
  'SubagentStart', 'SubagentStop', 'Stop', 'TeammateIdle', 'TaskCompleted',
  'Notification', 'ConfigChange', 'PreCompact', 'PostCompact', 'SessionEnd',
]);

const MATCHER_EVENTS = new Set([
  'InstructionsLoaded', 'PreToolUse', 'PermissionRequest', 'PermissionDenied',
  'PostToolUse', 'PostToolUseFailure',
]);

const VALID_HOOK_RECORD_KEYS = new Set(['matcher', 'hooks']);
const VALID_COMMAND_HOOK_KEYS = new Set(['type', 'command', 'async']);

function loadSettings() {
  return JSON.parse(readFileSync(SETTINGS_PATH, 'utf-8'));
}

function validateHookRecord(rec, event, expectsMatcher) {
  const errors = [];
  if (!('hooks' in rec)) errors.push(`${event}: missing required 'hooks' key - all events use nested format`);
  else if (!Array.isArray(rec.hooks)) errors.push(`${event}: 'hooks' must be an array`);
  else if (rec.hooks.length === 0) errors.push(`${event}: 'hooks' array must not be empty`);
  else {
    rec.hooks.forEach((hd, i) => {
      if (!hd || typeof hd !== 'object') { errors.push(`${event}.hooks[${i}]: must be an object`); return; }
      if (!('type' in hd)) errors.push(`${event}.hooks[${i}]: missing required 'type' key`);
      if (hd.type === 'command' && !('command' in hd)) errors.push(`${event}.hooks[${i}]: command hook missing required 'command' key`);
      const invalid = Object.keys(hd).filter((k) => !VALID_COMMAND_HOOK_KEYS.has(k));
      if (invalid.length) errors.push(`${event}.hooks[${i}]: invalid keys in command hook: ${invalid}`);
    });
  }
  if (expectsMatcher && !('matcher' in rec)) errors.push(`${event}: matcher-based event missing 'matcher' key`);
  const invalidKeys = Object.keys(rec).filter((k) => !VALID_HOOK_RECORD_KEYS.has(k));
  if (invalidKeys.length) errors.push(`${event}: invalid keys in hook record: ${invalidKeys}`);
  return errors;
}

test('settings.json is valid JSON object', () => {
  const s = loadSettings();
  assert.equal(typeof s, 'object');
  assert.ok(s !== null);
});

test('hooks section exists and is an object', () => {
  const s = loadSettings();
  assert.ok('hooks' in s);
  assert.equal(typeof s.hooks, 'object');
});

test('outputStyle stays Default for the coding profile', () => {
  assert.equal(loadSettings().outputStyle, 'Default');
});

test('all hook events are known types', () => {
  const events = new Set(Object.keys(loadSettings().hooks));
  const unknown = [...events].filter((e) => !HOOK_EVENTS.has(e));
  assert.deepEqual(unknown, []);
});

test('every hook event is a non-empty array', () => {
  const s = loadSettings();
  for (const [event, val] of Object.entries(s.hooks)) {
    assert.ok(Array.isArray(val), `${event}: must be an array`);
    assert.ok(val.length > 0, `${event}: array must not be empty`);
  }
});

test('all events use nested {hooks:[...]} format', () => {
  const s = loadSettings();
  for (const [event, arr] of Object.entries(s.hooks)) {
    arr.forEach((rec, i) => {
      assert.ok('hooks' in rec, `${event}[${i}]: missing 'hooks' key — ALL events must use nested format`);
      assert.ok(Array.isArray(rec.hooks), `${event}[${i}]: 'hooks' must be an array`);
    });
  }
});

test('matcher-based events have matcher and hooks keys', () => {
  const s = loadSettings();
  for (const event of MATCHER_EVENTS) {
    if (!(event in s.hooks)) continue;
    s.hooks[event].forEach((rec, i) => {
      assert.ok('matcher' in rec, `${event}[${i}]: matcher-based event missing 'matcher' key`);
      assert.ok('hooks' in rec, `${event}[${i}]: matcher-based event missing 'hooks' key`);
      assert.ok(Array.isArray(rec.hooks), `${event}[${i}]: 'hooks' must be an array`);
    });
  }
});

test('PostToolUse tracks all file-write tools (Edit|MultiEdit|Write|NotebookEdit)', () => {
  const post = loadSettings().hooks.PostToolUse || [];
  const matchers = new Set(post.map((h) => h.matcher || ''));
  assert.ok(matchers.has('Edit|MultiEdit|Write|NotebookEdit'));
});

test('Notification hook targets the notification script and is async', () => {
  const notif = loadSettings().hooks.Notification || [];
  assert.ok(notif.length, 'Notification hook must be configured');
  const rec = notif[0];
  assert.ok(!('matcher' in rec), 'Notification hook should use the non-matcher form in this profile');
  const nested = rec.hooks || [];
  assert.ok(nested.length, 'Notification hook must define nested hooks');
  const hd = nested[0];
  assert.equal(hd.type, 'command');
  assert.equal(hd.command, '"$HOME"/.claude/hooks/notification.sh');
  assert.equal(hd.async, true);
});

test('non-matcher events do not carry a matcher key', () => {
  const s = loadSettings();
  const nonMatcher = [...HOOK_EVENTS].filter((e) => !MATCHER_EVENTS.has(e));
  for (const event of nonMatcher) {
    if (!(event in s.hooks)) continue;
    s.hooks[event].forEach((rec, i) => {
      assert.ok(!('matcher' in rec), `${event}[${i}]: 'matcher' only valid for matcher events`);
    });
  }
});

test('no invalid keys in hook records', () => {
  const s = loadSettings();
  for (const [event, arr] of Object.entries(s.hooks)) {
    const expectsMatcher = MATCHER_EVENTS.has(event);
    arr.forEach((rec, i) => {
      const errors = validateHookRecord(rec, `${event}[${i}]`, expectsMatcher);
      assert.deepEqual(errors, [], `Validation errors: ${errors.join('; ')}`);
    });
  }
});

test('hook definitions have required type and command keys', () => {
  const s = loadSettings();
  for (const [event, arr] of Object.entries(s.hooks)) {
    arr.forEach((rec, i) => {
      const list = rec.hooks || [];
      list.forEach((hd, ni) => {
        assert.ok('type' in hd, `${event}[${i}].hooks[${ni}]: missing 'type' key`);
        if (hd.type === 'command') assert.ok('command' in hd, `${event}[${i}].hooks[${ni}]: command hook missing 'command' key`);
      });
    });
  }
});

test('regression: no flat format without hooks key', () => {
  const s = loadSettings();
  for (const [event, arr] of Object.entries(s.hooks)) {
    arr.forEach((rec, i) => {
      assert.ok('hooks' in rec, `${event}[${i}]: CRITICAL - missing 'hooks' key causes 'Invalid key in record'`);
    });
  }
});