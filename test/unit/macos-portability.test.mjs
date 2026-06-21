// Node port of tests/test_macos_portability.py — verifies no GNU/Linux-only
// constructs remain in shell scripts that must run on macOS (BSD userland +
// bash 3.2). The validate.sh-specific assertions were dropped because
// scripts/validate.sh was ported to Node ESM (scripts/validate.mjs); the
// install-smoke.sh and claudecfg/hooks/*.sh portability guards remain.
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

const REPO = join(import.meta.dirname, '..', '..');
const TESTS_INSTALL_DIR = join(REPO, 'tests', 'install');
const HOOKS_DIR = join(REPO, 'claudecfg', 'hooks');

const GNU_ONLY_PATTERNS = [
  ['declare -A', /\bdeclare\s+-A\b/],
  ['grep -P', /\bgrep\s+-P\b/],
  ['flock', /\bflock\b/],
  ['mapfile', /\bmapfile\b/],
  ['readarray', /\breadarray\b/],
  ['${var,,}', /\$\{[^}]*,,[^}]*\}/],
  ['find -printf', /\bfind\b[^;]*-printf\b/],
];

function listSh(dir) {
  return readdirSync(dir).filter((f) => f.endsWith('.sh')).map((f) => join(dir, f))
    .filter((p) => { try { return statSync(p).isFile(); } catch { return false; } });
}

function nonCommentLines(content) {
  return content.split('\n').filter((line) => {
    const s = line.trim();
    return !s.startsWith('#') && !s.startsWith('#!/');
  });
}

test('tests/install/install-smoke.sh probes sha256sum vs shasum -a 256', () => {
  const content = readFileSync(join(TESTS_INSTALL_DIR, 'install-smoke.sh'), 'utf-8');
  assert.ok(content.includes('sha256sum') && content.includes('shasum'),
    'tests/install/install-smoke.sh must probe for sha256sum vs shasum -a 256 to work on stock macOS');
});

test('tests/install/install-smoke.sh has no bare sha256sum calls', () => {
  const content = readFileSync(join(TESTS_INSTALL_DIR, 'install-smoke.sh'), 'utf-8');
  const bare = [];
  for (const [i, line] of content.split('\n').entries()) {
    const s = line.trim();
    if (s.startsWith('#') || s.startsWith('#!/')) continue;
    if (line.includes('sha256sum') && !line.includes('command -v sha256sum')) {
      if (/\bsha256sum\b/.test(line) && !/\$\{?SHA256/.test(line) && !/\bSHA256_CMD\s*=.*sha256sum/.test(line)) {
        bare.push([i + 1, s]);
      }
    }
  }
  assert.deepEqual(bare, [], `bare 'sha256sum' calls must go through a probed variable: ${JSON.stringify(bare)}`);
});

// Per-hook GNU-construct regression guards.
for (const script of listSh(HOOKS_DIR)) {
  const name = script.split('/').pop();
  const content = readFileSync(script, 'utf-8');
  const code = nonCommentLines(content).join('\n');

  test(`${name}: no flock (Linux-only)`, () => {
    assert.equal(code.match(/\bflock\b/g), null, `${name} uses 'flock' — use mkdir atomic locking instead`);
  });
  test(`${name}: no mapfile (bash 4+)`, () => {
    assert.equal(content.match(/\bmapfile\b/g), null, `${name} uses 'mapfile' — use 'while IFS= read -r' instead`);
  });
  test(`${name}: no readarray (bash 4+)`, () => {
    assert.equal(content.match(/\breadarray\b/g), null, `${name} uses 'readarray' — use 'while IFS= read -r' instead`);
  });
  test(`${name}: no declare -A (bash 4+)`, () => {
    assert.equal(content.match(/\bdeclare\s+-A\b/g), null, `${name} uses 'declare -A' — use parallel indexed arrays instead`);
  });
  test(`${name}: no grep -P (BSD grep lacks PCRE)`, () => {
    assert.equal(code.match(/\bgrep\s+-P\b/g), null, `${name} uses 'grep -P' — use 'sed -E' instead`);
  });
  test(`${name}: no \${var,,} case-folding (bash 4+)`, () => {
    assert.equal(code.match(/\$\{[^}]*,,[^}]*\}/g), null, `${name} uses '\${var,,}' — use 'tr \"[:upper:]\" \"[:lower:]\"' instead`);
  });
  test(`${name}: no find -printf (GNU extension)`, () => {
    assert.equal(code.match(/\bfind\b[^;]*-printf\b/g), null, `${name} uses 'find -printf' — use 'find … | sed' instead`);
  });
  test(`${name}: stat -c%s is guarded by a BSD fallback`, () => {
    const lines = content.split('\n');
    lines.forEach((line, i) => {
      if (/\bstat\s+-c%s\b/.test(line)) {
        const ctx = lines.slice(Math.max(0, i - 5), i + 5).join('\n');
        assert.ok(ctx.includes('stat -f%z'), `${name} line ${i + 1} uses 'stat -c%s' without a BSD fallback`);
      }
    });
  });
}