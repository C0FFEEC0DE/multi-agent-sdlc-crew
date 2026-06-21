import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import {
  classifyPrompt, taskTypeRequiresImplementationSummary,
  taskTypeRequiresSpecialistHandoffs, loopBlockFields, loopBlockCount,
  recordLoopBlock, clearLoopBlockPatch, userPromptResetPatch,
  sessionBackgroundManagerPending, STOP_SAFE_HINT,
} from '../../plugins/multi-agent-sdlc-crew/modules/workflow.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const fixtures = join(here, '..', '..', 'tests', 'hooks', 'fixtures');
function loadPrompt(name) {
  return JSON.parse(readFileSync(join(fixtures, `${name}.json`), 'utf8')).prompt;
}

// Fixture -> expected classification. Each row preserves the task type and
// role state the migrated UserPromptSubmit hook must produce.
const EXPECT = [
  ['user_prompt_feature', { taskType: 'feature', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['e', 'a']], ctx: 'feature workflow' }],
  ['user_prompt_bugfix', { taskType: 'bugfix', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['bug', 'e', 'dbg']], ctx: 'bugfix workflow' }],
  ['user_prompt_bugfix_ru', { taskType: 'bugfix', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['bug', 'e', 'dbg']], ctx: 'bugfix workflow' }],
  ['user_prompt_refactor', { taskType: 'refactor', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['a', 'e']], ctx: 'refactor workflow' }],
  ['user_prompt_review', { taskType: 'review', managerMode: 'none', docsRequired: false, requiredSubagents: ['cr'], anyOf: [], ctx: '@cr' }],
  ['user_prompt_docs', { taskType: 'docs', managerMode: 'none', docsRequired: true, requiredSubagents: ['doc'], anyOf: [], ctx: '@doc' }],
  ['user_prompt_model_question', { taskType: 'other', managerMode: 'none', docsRequired: false, requiredSubagents: [], anyOf: [], ctx: '' }],
  ['user_prompt_models_info', { taskType: 'other', managerMode: 'none', docsRequired: false, requiredSubagents: [], anyOf: [], ctx: '' }],
  ['user_prompt_models_creative_typo_info', { taskType: 'other', managerMode: 'none', docsRequired: false, requiredSubagents: [], anyOf: [], ctx: '' }],
  ['user_prompt_models_compare_repo', { taskType: 'other', managerMode: 'none', docsRequired: false, requiredSubagents: [], anyOf: [], ctx: '' }],
  ['user_prompt_models_feature', { taskType: 'feature', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['e', 'a']], ctx: 'feature workflow' }],
  ['user_prompt_models_mixed_feature', { taskType: 'feature', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['e', 'a']], ctx: 'feature workflow' }],
  ['user_prompt_models_manager_plan_only', { taskType: 'feature', managerMode: 'plan_only', docsRequired: true, requiredSubagents: [], anyOf: [], ctx: 'Plan-only' }],
  ['user_prompt_models_review', { taskType: 'review', managerMode: 'none', docsRequired: false, requiredSubagents: ['cr'], anyOf: [], ctx: '@cr' }],
  ['user_prompt_models_docs', { taskType: 'docs', managerMode: 'none', docsRequired: true, requiredSubagents: ['doc'], anyOf: [], ctx: '@doc' }],
  ['user_prompt_tech_support_bug_word', { taskType: 'support', managerMode: 'none', docsRequired: false, requiredSubagents: [], anyOf: [], ctx: 'support workflow' }],
  ['user_prompt_benchmark_refactor_override', { taskType: 'refactor', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['a', 'e']], ctx: 'refactor workflow' }],
  ['user_prompt_mixed_intent', { taskType: 'bugfix', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['bug', 'e', 'dbg']], ctx: 'bugfix workflow' }],
  ['user_prompt_hey', { taskType: 'other', managerMode: 'none', docsRequired: false, requiredSubagents: [], anyOf: [], ctx: '' }],
  ['user_prompt_manager_plan_only', { taskType: 'feature', managerMode: 'plan_only', docsRequired: true, requiredSubagents: [], anyOf: [], ctx: 'Plan-only' }],
  ['user_prompt_no_session_id', { taskType: 'feature', managerMode: 'none', docsRequired: true, requiredSubagents: ['t', 'cr'], anyOf: [['e', 'a']], ctx: 'feature workflow' }],
];

for (const [name, exp] of EXPECT) {
  test(`classifyPrompt: ${name} -> ${exp.taskType}/${exp.managerMode}`, () => {
    const r = classifyPrompt(loadPrompt(name));
    assert.equal(r.taskType, exp.taskType, `taskType for ${name}`);
    assert.equal(r.managerMode, exp.managerMode, `managerMode for ${name}`);
    assert.equal(r.docsRequired, exp.docsRequired, `docsRequired for ${name}`);
    assert.deepEqual(r.requiredSubagents, exp.requiredSubagents, `requiredSubagents for ${name}`);
    assert.deepEqual(r.requiredSubagentAnyOf, exp.anyOf, `requiredSubagentAnyOf for ${name}`);
    if (exp.ctx === '') assert.equal(r.contextMessage, '', `contextMessage for ${name} should be empty`);
    else assert.ok(r.contextMessage.includes(exp.ctx), `contextMessage for ${name} should contain "${exp.ctx}", got: ${r.contextMessage}`);
  });
}

test('stop-safe hint appears on non-plan-only gated contexts', () => {
  const r = classifyPrompt(loadPrompt('user_prompt_feature'));
  assert.ok(r.contextMessage.includes(STOP_SAFE_HINT.trim().slice(0, 40)));
});

test('plan-only context omits the stop-safe hint', () => {
  const r = classifyPrompt(loadPrompt('user_prompt_models_manager_plan_only'));
  assert.ok(!r.contextMessage.includes('If a later reply'));
});

// --- task type predicates --------------------------------------------------

test('taskTypeRequiresImplementationSummary', () => {
  for (const t of ['feature', 'bugfix', 'refactor', 'review', 'docs']) {
    assert.equal(taskTypeRequiresImplementationSummary(t), true, t);
  }
  for (const t of ['support', 'other', '', 'random']) {
    assert.equal(taskTypeRequiresImplementationSummary(t), false, t);
  }
});

test('taskTypeRequiresSpecialistHandoffs', () => {
  for (const t of ['feature', 'bugfix', 'refactor', 'review', 'docs', 'support']) {
    assert.equal(taskTypeRequiresSpecialistHandoffs(t), true, t);
  }
  for (const t of ['other', '', 'random']) {
    assert.equal(taskTypeRequiresSpecialistHandoffs(t), false, t);
  }
});

// --- loop-block accounting -------------------------------------------------

test('loopBlockFields maps stop and subagent_stop, rejects others', () => {
  assert.deepEqual(loopBlockFields('stop'), { countKey: 'stop_block_count', reasonKey: 'stop_block_reason', messageKey: 'stop_block_message' });
  assert.deepEqual(loopBlockFields('subagent_stop'), { countKey: 'subagent_stop_block_count', reasonKey: 'subagent_stop_block_reason', messageKey: 'subagent_stop_block_message' });
  assert.equal(loopBlockFields('nope'), null);
});

test('recordLoopBlock increments on matching reason+message, resets otherwise', () => {
  const s = { stop_block_count: 2, stop_block_reason: 'r', stop_block_message: 'm' };
  assert.deepEqual(recordLoopBlock(s, 'stop', 'r', 'm'), { stop_block_count: 3, stop_block_reason: 'r', stop_block_message: 'm' });
  assert.deepEqual(recordLoopBlock(s, 'stop', 'r2', 'm'), { stop_block_count: 1, stop_block_reason: 'r2', stop_block_message: 'm' });
  assert.equal(recordLoopBlock(s, 'bad', 'r', 'm'), null);
});

test('loopBlockCount reads defensively', () => {
  assert.equal(loopBlockCount({ stop_block_count: 5 }, 'stop'), 5);
  assert.equal(loopBlockCount({}, 'stop'), 0);
  assert.equal(loopBlockCount({ subagent_stop_block_count: 3 }, 'subagent_stop'), 3);
  assert.equal(loopBlockCount({}, 'bad'), 0);
});

test('clearLoopBlockPatch zeroes fields and policy-stall state', () => {
  assert.deepEqual(clearLoopBlockPatch('stop'), {
    stop_block_count: 0, stop_block_reason: '', stop_block_message: '',
    stalled_by_policy: false, policy_stall_reason: '',
  });
  assert.deepEqual(clearLoopBlockPatch('subagent_stop'), {
    subagent_stop_block_count: 0, subagent_stop_block_reason: '', subagent_stop_block_message: '',
    stalled_by_policy: false, policy_stall_reason: '',
  });
  assert.equal(clearLoopBlockPatch('bad'), null);
});

test('userPromptResetPatch resets the stop loop', () => {
  assert.deepEqual(userPromptResetPatch(), {
    stop_block_count: 0, stop_block_reason: '', stop_block_message: '',
    stalled_by_policy: false, policy_stall_reason: '',
  });
});

// --- session_background_manager_pending ------------------------------------

test('sessionBackgroundManagerPending gating', () => {
  const base = { taskType: 'feature', managerMode: 'orchestrate', codeChanged: false, backgroundedAgent: true, startedRoles: ['m'] };
  assert.equal(sessionBackgroundManagerPending(base), true);
  assert.equal(sessionBackgroundManagerPending({ ...base, taskType: 'other' }), false);
  assert.equal(sessionBackgroundManagerPending({ ...base, managerMode: 'none' }), false);
  assert.equal(sessionBackgroundManagerPending({ ...base, codeChanged: true }), false);
  assert.equal(sessionBackgroundManagerPending({ ...base, backgroundedAgent: false }), false);
  assert.equal(sessionBackgroundManagerPending({ ...base, startedRoles: ['e'] }), false);
  assert.equal(sessionBackgroundManagerPending({ ...base, taskType: 'support' }), false);
});