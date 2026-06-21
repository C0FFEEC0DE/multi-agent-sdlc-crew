// Node tests for scripts/assert-benchmark-summary.mjs (port of the Python test).
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { summaryPassesGate } from '../../scripts/assert-benchmark-summary.mjs';

const REPO = join(import.meta.dirname, '..', '..');
const SCRIPT = join(REPO, 'scripts', 'assert-benchmark-summary.mjs');

function passingTotals() {
  return {
    configured_tasks: 2, selected_tasks: 2, executed_tasks: 2, unexecuted_tasks: 0,
    unresolved_tasks: 0, tasks: 2, passed: 2, clean_passed: 2, completed: 2,
    verification_required: 2, tests_run: 2, review_required: 2, review_present: 2,
    docs_required: 0, docs_updated: 0, recovered_tasks: 0, timeout_recovered: 0,
    max_turns_recovered: 0, summary_repaired: 0, policy_violations: 0, tool_failures: 0,
  };
}
function summary(overrides = {}) {
  const totals = passingTotals();
  if (overrides.totals) Object.assign(totals, overrides.totals);
  const { totals: _omit, ...rest } = overrides;
  return {
    schema_version: '1.0', mode: 'cmd', runner: 'r', generated_at: 'x',
    source_ref: 'ref', source_sha: 'sha', task_glob: 'g', totals,
    rates: { task_pass_rate: 1, clean_pass_rate: 1, completion_rate: 1, verification_pass_rate: 1, review_compliance_rate: 1, docs_compliance_rate: 1, execution_coverage_rate: 1, recovered_task_rate: 0, summary_repair_rate: 0 },
    median_runtime_seconds: 1, tasks: [], ...rest,
  };
}
function runCli(file, extraEnv = {}) {
  return spawnSync(process.execPath, [SCRIPT, file], { encoding: 'utf-8', env: { ...process.env, ...extraEnv } });
}

test('passing summary exits zero', () => {
  const d = mkdtempSync(join(tmpdir(), 'assert-'));
  const f = join(d, 'summary.json');
  writeFileSync(f, JSON.stringify(summary()));
  const r = runCli(f);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /Checking summary file/);
});

test('missing file exits one', () => {
  const r = runCli(join(tmpdir(), 'nope-' + Date.now() + '.json'));
  assert.equal(r.status, 1);
  assert.match(r.stderr, /not found/);
});

test('wrong arg count exits one', () => {
  const r = spawnSync(process.execPath, [SCRIPT], { encoding: 'utf-8' });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /Usage/);
});

test('executed != configured fails', () => {
  assert.equal(summaryPassesGate(summary({ totals: { configured_tasks: 2, executed_tasks: 1, tasks: 1, passed: 1 } })), false);
});
test('passed != tasks fails', () => {
  assert.equal(summaryPassesGate(summary({ totals: { passed: 1 } })), false);
});
test('tool_failures fails', () => {
  assert.equal(summaryPassesGate(summary({ totals: { tool_failures: 1 } })), false);
});
test('policy_violations fails', () => {
  assert.equal(summaryPassesGate(summary({ totals: { policy_violations: 1 } })), false);
});
test('unresolved_tasks fails', () => {
  assert.equal(summaryPassesGate(summary({ totals: { unresolved_tasks: 1 } })), false);
});
test('zero configured fails', () => {
  assert.equal(summaryPassesGate(summary({ totals: { configured_tasks: 0, executed_tasks: 0, tasks: 0, passed: 0 } })), false);
});
test('missing unresolved field treated as zero passes', () => {
  const s = summary(); delete s.totals.unresolved_tasks;
  assert.equal(summaryPassesGate(s), true);
});
test('recovered ceiling passes when under', () => {
  assert.equal(summaryPassesGate(summary({ totals: { recovered_tasks: 2 } }), { maxRecoveredTasks: '2' }), true);
});
test('recovered ceiling fails when over', () => {
  assert.equal(summaryPassesGate(summary({ totals: { recovered_tasks: 3 } }), { maxRecoveredTasks: '2' }), false);
});
test('summary repaired ceiling passes when under', () => {
  assert.equal(summaryPassesGate(summary({ totals: { summary_repaired: 1 } }), { maxSummaryRepairedTasks: '1' }), true);
});
test('summary repaired ceiling fails when over', () => {
  assert.equal(summaryPassesGate(summary({ totals: { summary_repaired: 5 } }), { maxSummaryRepairedTasks: '2' }), false);
});
test('both ceilings set pass', () => {
  assert.equal(summaryPassesGate(summary({ totals: { recovered_tasks: 1, summary_repaired: 1 } }), { maxRecoveredTasks: '2', maxSummaryRepairedTasks: '2' }), true);
});