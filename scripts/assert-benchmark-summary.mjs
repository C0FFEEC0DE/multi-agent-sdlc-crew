#!/usr/bin/env node
// assert-benchmark-summary: CI gate that decides whether a benchmark run passed.
// Node port of scripts/assert-benchmark-summary.sh — no jq, no Bash.
import { readFileSync, existsSync } from 'node:fs';
import { isMain } from './bench/lib.mjs';

function usage() {
  process.stderr.write('Usage: assert-benchmark-summary.mjs SUMMARY_JSON\n');
  process.exit(1);
}

function fail(msg) {
  process.stderr.write(`ERROR: ${msg}\n`);
  process.exit(1);
}

export function summaryPassesGate(summary, opts = {}) {
  const t = summary.totals || {};
  const maxRecovered = opts.maxRecoveredTasks;
  const maxRepaired = opts.maxSummaryRepairedTasks;
  const checks = [
    t.configured_tasks > 0,
    t.executed_tasks > 0,
    t.executed_tasks === t.configured_tasks,
    t.tasks === t.executed_tasks,
    t.passed === t.tasks,
    t.tool_failures === 0,
    t.policy_violations === 0,
    (t.unresolved_tasks ?? 0) === 0,
  ];
  if (maxRecovered !== undefined && maxRecovered !== null && maxRecovered !== '') {
    checks.push((t.recovered_tasks ?? 0) <= Number(maxRecovered));
  }
  if (maxRepaired !== undefined && maxRepaired !== null && maxRepaired !== '') {
    checks.push((t.summary_repaired ?? 0) <= Number(maxRepaired));
  }
  return checks.every(Boolean);
}

function main() {
  if (process.argv.length !== 3) usage();
  const summaryFile = process.argv[2];
  if (!existsSync(summaryFile)) {
    process.stderr.write(`ERROR: Summary file not found: ${summaryFile}\n`);
    process.exit(1);
  }
  process.stdout.write(`Checking summary file: ${summaryFile}\n`);
  process.stdout.write('File contents:\n');
  try {
    process.stderr.write(readFileSync(summaryFile, 'utf-8') + '\n');
  } catch {
    process.stderr.write('(cannot read file)\n');
  }
  let summary;
  try {
    summary = JSON.parse(readFileSync(summaryFile, 'utf-8'));
  } catch {
    fail('Benchmark summary is not valid JSON!');
  }
  const opts = {
    maxRecoveredTasks: process.env.BENCH_MAX_RECOVERED_TASKS ?? '',
    maxSummaryRepairedTasks: process.env.BENCH_MAX_SUMMARY_REPAIRED_TASKS ?? '',
  };
  if (!summaryPassesGate(summary, opts)) {
    process.stderr.write('ERROR: Benchmark summary failed gate check!\n');
    process.stderr.write('Summary contents:\n');
    process.stderr.write(readFileSync(summaryFile, 'utf-8') + '\n');
    process.exit(1);
  }
}

if (isMain(import.meta.url)) {
  main();
}