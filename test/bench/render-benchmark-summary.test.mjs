// Node tests for scripts/render-benchmark-summary.mjs (ports of the Python
// render-summary test and the bench_runner task-status-table test).
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { renderSummary } from '../../scripts/render-benchmark-summary.mjs';

const REPO = join(import.meta.dirname, '..', '..');
const SCRIPT = join(REPO, 'scripts', 'render-benchmark-summary.mjs');

function runCli(summaryPath) {
  return spawnSync(process.execPath, [SCRIPT, summaryPath], { encoding: 'utf-8' });
}

function baseSummary() {
  return {
    schema_version: '1.0', mode: 'cmd', runner: 'r', generated_at: 'x',
    source_ref: 'ref', source_sha: 'sha', task_glob: 'g',
    totals: { configured_tasks: 0, selected_tasks: 0, executed_tasks: 0, unexecuted_tasks: 0, unresolved_tasks: 0, passed: 0, clean_passed: 0, completed: 0, verification_required: 0, tests_run: 0, review_required: 0, review_present: 0, docs_required: 0, docs_updated: 0, recovered_tasks: 0, timeout_recovered: 0, max_turns_recovered: 0, summary_repaired: 0, policy_violations: 0, tool_failures: 0 },
    rates: { task_pass_rate: 0, clean_pass_rate: 0, completion_rate: 0, verification_rate: 0, verification_pass_rate: 0, review_compliance_rate: 0, docs_compliance_rate: 0, recovered_task_rate: 0, summary_repair_rate: 0, execution_coverage_rate: 0, unexecuted_rate: 0, unresolved_rate: 0 },
    median_runtime_seconds: 0, selected_task_ids: [], selected_task_paths: [], executed_task_ids: [], executed_task_paths: [], unexecuted_task_ids: [], unexecuted_task_paths: [], unresolved_task_ids: [], unresolved_task_paths: [], tasks: [],
  };
}

test('render summary produces markdown overview', () => {
  const d = mkdtempSync(join(tmpdir(), 'rs-'));
  const s = baseSummary();
  s.totals = { ...s.totals, configured_tasks: 1, selected_tasks: 2, executed_tasks: 1, unexecuted_tasks: 1, unresolved_tasks: 1, passed: 1, clean_passed: 1, completed: 1 };
  s.rates = { ...s.rates, task_pass_rate: 1, clean_pass_rate: 1, completion_rate: 1, verification_pass_rate: 1, review_compliance_rate: 1, docs_compliance_rate: 1, execution_coverage_rate: 1, unexecuted_rate: 0.5, unresolved_rate: 0.5 };
  s.median_runtime_seconds = 10;
  s.selected_task_ids = ['test-task', 'resume-task'];
  s.selected_task_paths = ['bench/tasks/smoke/test-task.json', 'bench/tasks/smoke/resume-task.json'];
  s.executed_task_ids = ['test-task'];
  s.executed_task_paths = ['bench/tasks/smoke/test-task.json'];
  s.unexecuted_task_ids = ['resume-task'];
  s.unexecuted_task_paths = ['bench/tasks/smoke/resume-task.json'];
  s.unresolved_task_ids = ['resume-task'];
  s.unresolved_task_paths = ['bench/tasks/smoke/resume-task.json'];
  s.tasks = [{ task_id: 'test-task', status: 'passed', completed: true, runtime_seconds: 10, verification_required: false, tests_run: false, tests_passed: false, review_required: false, review_present: true, docs_required: false, docs_updated: true, recovered_nonzero_exit: false, timeout_recovered: false, max_turns_recovered: false, summary_repaired_by: 'none', changed_files: [], failures: [] }];
  const f = join(d, 'summary.json');
  writeFileSync(f, JSON.stringify(s));
  const r = runCli(f);
  assert.equal(r.status, 0, r.stderr);
  assert.match(r.stdout, /### Overview/);
  assert.match(r.stdout, /\| Configured tasks \| 1 \|/);
  assert.match(r.stdout, /\| Selected tasks \| 2 \|/);
  assert.match(r.stdout, /\| Unexecuted tasks \| 1 \|/);
  assert.match(r.stdout, /\| Unresolved tasks \| 1 \|/);
  assert.match(r.stdout, /\| Pass rate \| 100% \|/);
  assert.match(r.stdout, /`test-task`/);
  assert.match(r.stdout, /### Unexecuted Tasks/);
  assert.match(r.stdout, /### Unresolved Tasks/);
  assert.match(r.stdout, /resume-task/);
});

test('render summary zero tasks', () => {
  const d = mkdtempSync(join(tmpdir(), 'rs-'));
  const f = join(d, 'summary.json');
  writeFileSync(f, JSON.stringify(baseSummary()));
  const r = runCli(f);
  assert.equal(r.status, 0);
  assert.match(r.stdout, /### Overview/);
  assert.match(r.stdout, /No executed tasks/);
});

test('task status table row matches jq byte-for-byte', () => {
  const s = baseSummary();
  s.totals = { ...s.totals, configured_tasks: 3, executed_tasks: 2, recovered_tasks: 1, summary_repaired: 0 };
  s.rates = { ...s.rates, execution_coverage_rate: 2 / 3, task_pass_rate: 0.5, clean_pass_rate: 0.5 };
  s.median_runtime_seconds = 12.34;
  s.tasks = [
    { task_id: 'bugfix-zero-division-lite', status: 'passed', runtime_seconds: 10.5, verification_required: true, tests_run: true, tests_passed: true, review_required: true, review_present: true, docs_required: true, docs_updated: true, changed_files: ['calculator.py', 'README.md'], recovered_nonzero_exit: false, timeout_recovered: false, max_turns_recovered: false, summary_repaired_by: 'none', failures: [] },
    { task_id: 'feature-manager-no-agent-choice', status: 'failed', runtime_seconds: 14.18, verification_required: true, tests_run: true, tests_passed: false, review_required: true, review_present: true, docs_required: true, docs_updated: true, changed_files: ['calculator.py', 'test_calculator.py', 'README.md'], recovered_nonzero_exit: true, timeout_recovered: true, max_turns_recovered: false, summary_repaired_by: 'retry', failures: ['verification_failed', 'required_used_agents_missing'] },
  ];
  const out = renderSummary(s);
  assert.match(out, /\| `bugfix-zero-division-lite` \| `passed` \| 10.5 \| `passed` \| `done` \| `updated` \| calculator.py, README.md \| `none` \| `none` \| — \|/);
  assert.match(out, /\| `feature-manager-no-agent-choice` \| `failed` \| 14.18 \| `failed` \| `done` \| `updated` \| calculator.py, test_calculator.py, README.md \| `timeout` \| `retry` \| verification_failed, required_used_agents_missing \|/);
  assert.match(out, /> Note: only 2 of 3 selected tasks executed./);
});