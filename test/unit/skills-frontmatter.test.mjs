// Node port of tests/test_skills_frontmatter.py — validates YAML frontmatter
// contract for bundled slash skills under claudecfg/skills.
import { test } from 'node:test';
import { strict as assert } from 'node:assert';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, basename } from 'node:path';

const REPO = join(import.meta.dirname, '..', '..');
const SKILL_DIR = join(REPO, 'claudecfg', 'skills');
const AGENT_DIR = join(REPO, 'claudecfg', 'agents');

const REQUIRED_FIELDS = ['name', 'description', 'agent', 'context', 'disable-model-invocation', 'allowed-tools', 'paths'];

// readdirSync with stat follow (symlinks), mirroring the bash glob used for
// agent/skill files.
function listMd(dir) {
  return readdirSync(dir).filter((f) => f.endsWith('.md')).map((f) => join(dir, f))
    .filter((p) => { try { return statSync(p).isFile(); } catch { return false; } })
    .sort();
}

function extractFrontmatter(mdPath) {
  const lines = readFileSync(mdPath, 'utf-8').split('\n');
  assert.ok(lines.length, `${basename(mdPath)}: file is empty`);
  assert.equal(lines[0].trim(), '---', `${basename(mdPath)}: missing frontmatter start delimiter`);
  let end = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === '---') { end = i; break; }
  }
  assert.ok(end !== -1, `${basename(mdPath)}: missing frontmatter end delimiter`);
  if (end + 1 < lines.length) {
    assert.notEqual(lines[end + 1].trim(), '---', `${basename(mdPath)}: duplicate frontmatter block detected`);
  }
  return lines.slice(1, end);
}

function extractScalar(fm, field) {
  const prefix = `${field}:`;
  for (const line of fm) {
    if (line.startsWith(prefix)) return line.slice(prefix.length).trim();
  }
  assert.fail(`missing frontmatter field '${field}'`);
}

function extractList(fm, field) {
  const items = [];
  let capture = false;
  for (const line of fm) {
    const stripped = line.trim();
    if (stripped.startsWith(`${field}:`)) {
      const inline = stripped.slice(field.length + 1).trim();
      if (inline) items.push(inline);
      capture = true;
      continue;
    }
    if (capture && stripped.startsWith('- ')) { items.push(stripped.slice(2).trim()); continue; }
    if (capture && stripped && !stripped.startsWith('#')) break;
  }
  return items;
}

test('all skills have required frontmatter fields with pinned context/disable flags', () => {
  const files = listMd(SKILL_DIR);
  assert.ok(files.length, 'No skills found under claudecfg/skills');
  for (const sf of files) {
    const fm = extractFrontmatter(sf);
    const text = fm.join('\n');
    for (const field of REQUIRED_FIELDS) {
      assert.ok(fm.some((l) => l.startsWith(`${field}:`)), `${basename(sf)}: missing required frontmatter field '${field}'`);
    }
    assert.ok(text.includes('disable-model-invocation: true'), `${basename(sf)}: must pin disable-model-invocation: true`);
    assert.ok(text.includes('context: fork'), `${basename(sf)}: must pin context: fork`);
  }
});

test('allowed-tools and paths are non-empty lists', () => {
  for (const sf of listMd(SKILL_DIR)) {
    const fm = extractFrontmatter(sf);
    const tools = extractList(fm, 'allowed-tools');
    const paths = extractList(fm, 'paths');
    assert.ok(tools.length, `${basename(sf)}: allowed-tools must declare at least one tool`);
    assert.ok(paths.length, `${basename(sf)}: paths must declare at least one path`);
  }
});

test('skill agents match a known agent name or alias', () => {
  const known = new Set();
  for (const af of listMd(AGENT_DIR)) {
    const fm = extractFrontmatter(af);
    known.add(extractScalar(fm, 'name'));
    known.add(extractScalar(fm, 'alias'));
  }
  for (const sf of listMd(SKILL_DIR)) {
    const fm = extractFrontmatter(sf);
    const agent = extractScalar(fm, 'agent');
    assert.ok(known.has(agent), `${basename(sf)}: agent must match a known agent name or alias`);
  }
});