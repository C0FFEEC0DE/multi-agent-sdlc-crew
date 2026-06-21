// Tests for scripts/check-no-legacy-runtime.mjs
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { mkdirSync, writeFileSync, rmSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { checkNoLegacyRuntime, SCRIPTS_ALLOWLIST } from '../../scripts/check-no-legacy-runtime.mjs';
import { tmpdir } from 'node:os';

function makeTree(root) {
  // Clean plugin runtime (Node-only) + allowlisted CI runners + a Node script.
  mkdirSync(join(root, 'plugins', 'multi-agent-sdlc-crew', 'scripts'), { recursive: true });
  writeFileSync(join(root, 'plugins', 'multi-agent-sdlc-crew', 'scripts', 'statusline.mjs'), '// node\n');
  mkdirSync(join(root, 'scripts'), { recursive: true });
  writeFileSync(join(root, 'scripts', 'bench_runner_claude_code.py'), '# ci runner\n');
  writeFileSync(join(root, 'scripts', 'bench_runner_openrouter.py'), '# ci runner\n');
  writeFileSync(join(root, 'scripts', 'lint.mjs'), '// node\n');
}

function freshRoot() {
  const root = join(tmpdir(), `legacy-gate-${Date.now()}-${Math.random().toString(36).slice(2)}`);
  mkdirSync(root, { recursive: true });
  return root;
}

test('passes on a clean tree with the two allowlisted runners', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, true);
    assert.equal(r.offenses.length, 0);
    assert.deepEqual(r.allowlisted.sort(), ['scripts/bench_runner_claude_code.py', 'scripts/bench_runner_openrouter.py']);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('fails when a stray .sh is placed under plugins/', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    writeFileSync(join(root, 'plugins', 'multi-agent-sdlc-crew', 'legacy.sh'), '#!/bin/bash\nexit 0\n');
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, false);
    assert.ok(r.offenses.some((o) => o.includes('legacy.sh') && o.includes('plugin runtime')));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('fails when a stray .py appears under plugins/', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    writeFileSync(join(root, 'plugins', 'multi-agent-sdlc-crew', 'helper.py'), 'print(1)\n');
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, false);
    assert.ok(r.offenses.some((o) => o.includes('helper.py')));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('fails when a non-allowlisted .py appears in scripts/', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    writeFileSync(join(root, 'scripts', 'stray.py'), 'print(1)\n');
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, false);
    assert.ok(r.offenses.some((o) => o.includes('stray.py') && o.includes('non-allowlisted')));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('fails when a non-allowlisted .sh appears in scripts/', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    writeFileSync(join(root, 'scripts', 'stray.sh'), '#!/bin/bash\nexit 0\n');
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, false);
    assert.ok(r.offenses.some((o) => o.includes('stray.sh')));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('a same-named .py nested in a subdir is NOT allowlisted', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    // A spoof file whose basename matches an allowlisted runner but lives in a
    // subdir must be flagged — the allowlist matches the full relative path.
    mkdirSync(join(root, 'scripts', 'sub'), { recursive: true });
    writeFileSync(join(root, 'scripts', 'sub', 'bench_runner_claude_code.py'), '# spoof\n');
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, false);
    assert.ok(r.offenses.some((o) => o.includes('scripts/sub/bench_runner_claude_code.py')));
    // The real allowlisted runner is still listed.
    assert.ok(r.allowlisted.includes('scripts/bench_runner_claude_code.py'));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('allowlist entries pass (named runners not flagged)', () => {
  const root = freshRoot();
  try {
    makeTree(root);
    // Only the two allowlisted runners exist under scripts/.
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, true);
    // SCRIPTS_ALLOWLIST contract: two entries, each with a rationale.
    assert.equal(SCRIPTS_ALLOWLIST.length, 2);
    for (const a of SCRIPTS_ALLOWLIST) {
      assert.ok(a.file.endsWith('.py'));
      assert.ok(a.reason && a.reason.length > 0);
    }
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test('missing plugins dir is not an error (empty offenses for plugin scan)', () => {
  const root = freshRoot();
  try {
    mkdirSync(join(root, 'scripts'), { recursive: true });
    writeFileSync(join(root, 'scripts', 'lint.mjs'), '// node\n');
    const r = checkNoLegacyRuntime(root);
    assert.equal(r.ok, true);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});