// Shared helpers for the Node benchmark CLIs.
// Node standard library only — no Python, Bash, jq, or external deps.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { spawnSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';

/** True when this module is the entry point (node scripts/foo.mjs). */
export function isMain(importMetaUrl) {
  if (!process.argv[1]) return false;
  try {
    return pathToFileURL(process.argv[1]).href === importMetaUrl;
  } catch {
    return false;
  }
}

/** Read and parse a JSON file (UTF-8). Throws on missing/invalid JSON. */
export function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf-8'));
}

/**
 * A JSON number that retains its original literal text so renderers can match
 * jq's number-to-string (jq preserves `20.0` as "20.0"; JSON.parse collapses it
 * to 20). Arithmetic and comparisons work via valueOf; template-literal
 * interpolation uses the original literal via toString.
 */
export class JSONNum {
  constructor(literal, value) {
    this.literal = literal;
    this.value = value;
  }
  valueOf() { return this.value; }
  toString() { return this.literal; }
  toJSON() { return this.value; }
}

/**
 * Parse JSON preserving number literals as JSONNum so renderers can reproduce
 * jq's exact number formatting. Strings, booleans, and null are primitives;
 * objects/arrays are plain JS containers.
 */
export function parseJsonPreservingNumbers(text) {
  let i = 0;
  const n = text.length;
  function skipWs() {
    while (i < n) {
      const c = text[i];
      if (c === ' ' || c === '\t' || c === '\n' || c === '\r') i++;
      else break;
    }
  }
  function parseValue() {
    skipWs();
    const c = text[i];
    if (c === '{') return parseObject();
    if (c === '[') return parseArray();
    if (c === '"') return parseString();
    if (c === '-' || (c >= '0' && c <= '9')) return parseNumber();
    if (text.startsWith('true', i)) { i += 4; return true; }
    if (text.startsWith('false', i)) { i += 5; return false; }
    if (text.startsWith('null', i)) { i += 4; return null; }
    throw new SyntaxError(`Unexpected token at ${i}: ${JSON.stringify(text.slice(i, i + 20))}`);
  }
  function parseObject() {
    const obj = {};
    i++; // {
    skipWs();
    if (text[i] === '}') { i++; return obj; }
    while (true) {
      skipWs();
      const key = parseString();
      skipWs();
      if (text[i] !== ':') throw new SyntaxError(`Expected ':' at ${i}`);
      i++;
      obj[key] = parseValue();
      skipWs();
      if (text[i] === ',') { i++; continue; }
      if (text[i] === '}') { i++; break; }
      throw new SyntaxError(`Expected ',' or '}' at ${i}`);
    }
    return obj;
  }
  function parseArray() {
    const arr = [];
    i++; // [
    skipWs();
    if (text[i] === ']') { i++; return arr; }
    while (true) {
      arr.push(parseValue());
      skipWs();
      if (text[i] === ',') { i++; continue; }
      if (text[i] === ']') { i++; break; }
      throw new SyntaxError(`Expected ',' or ']' at ${i}`);
    }
    return arr;
  }
  function parseString() {
    if (text[i] !== '"') throw new SyntaxError(`Expected string at ${i}`);
    i++;
    let out = '';
    while (i < n) {
      const c = text[i];
      if (c === '"') { i++; return out; }
      if (c === '\\') {
        const e = text[i + 1];
        i += 2;
        if (e === '"') out += '"';
        else if (e === '\\') out += '\\';
        else if (e === '/') out += '/';
        else if (e === 'b') out += '\b';
        else if (e === 'f') out += '\f';
        else if (e === 'n') out += '\n';
        else if (e === 'r') out += '\r';
        else if (e === 't') out += '\t';
        else if (e === 'u') {
          out += String.fromCharCode(parseInt(text.slice(i, i + 4), 16));
          i += 4;
        } else throw new SyntaxError(`Bad escape \\${e}`);
      } else {
        out += c;
        i++;
      }
    }
    throw new SyntaxError('Unterminated string');
  }
  function parseNumber() {
    const start = i;
    if (text[i] === '-') i++;
    while (i < n && text[i] >= '0' && text[i] <= '9') i++;
    let isFloat = false;
    if (text[i] === '.') { isFloat = true; i++; while (i < n && text[i] >= '0' && text[i] <= '9') i++; }
    if (text[i] === 'e' || text[i] === 'E') {
      isFloat = true; i++;
      if (text[i] === '+' || text[i] === '-') i++;
      while (i < n && text[i] >= '0' && text[i] <= '9') i++;
    }
    const literal = text.slice(start, i);
    const value = Number(literal);
    return new JSONNum(literal, value);
  }
  const result = parseValue();
  skipWs();
  if (i !== n) throw new SyntaxError('Trailing characters in JSON');
  return result;
}

/** Read a JSON file preserving number literals (see parseJsonPreservingNumbers). */
export function readJsonPreserving(path) {
  return parseJsonPreservingNumbers(readFileSync(path, 'utf-8'));
}

/**
 * Serialize a value to JSON preserving JSONNum literals (so "20.0" stays
 * "20.0" rather than collapsing to "20"). Plain numbers use Number.toString,
 * matching jq's canonical rendering for computed values (drops trailing .0).
 * This mirrors jq's behavior: pass-through literals are preserved, computed
 * numbers use canonical form.
 */
export function stringifyJsonPreserving(value, indent = 2) {
  const space = ' '.repeat(indent);
  function rep(v, depth) {
    if (v === null) return 'null';
    if (v === undefined) return 'null';
    if (typeof v === 'boolean') return v ? 'true' : 'false';
    if (v instanceof JSONNum) return v.toString();
    if (typeof v === 'number') {
      if (!Number.isFinite(v)) return 'null';
      return v.toString();
    }
    if (typeof v === 'string') return JSON.stringify(v);
    if (Array.isArray(v)) {
      if (v.length === 0) return '[]';
      const inner = v.map((x) => space.repeat(depth + 1) + rep(x, depth + 1));
      return '[\n' + inner.join(',\n') + '\n' + space.repeat(depth) + ']';
    }
    if (typeof v === 'object') {
      const keys = Object.keys(v);
      if (keys.length === 0) return '{}';
      const inner = keys.map((k) => space.repeat(depth + 1) + JSON.stringify(k) + ': ' + rep(v[k], depth + 1));
      return '{\n' + inner.join(',\n') + '\n' + space.repeat(depth) + '}';
    }
    return JSON.stringify(v);
  }
  return rep(value, 0);
}

/** Read and parse a JSON file, returning null if it does not exist. */
export function readJsonOptional(path) {
  try {
    return JSON.parse(readFileSync(path, 'utf-8'));
  } catch (err) {
    if (err && err.code === 'ENOENT') return null;
    throw err;
  }
}

/** Write JSON with a trailing newline, creating parent dirs. */
export function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(value, null, 2) + '\n', 'utf-8');
}

/** Median of an array of numbers; 0 for empty input. */
export function median(values) {
  if (!values || values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  if (sorted.length % 2 === 1) return sorted[mid];
  return (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Safe rate: num/den, or 0 when den is 0. */
export function rate(num, den) {
  return den === 0 ? 0 : num / den;
}

/** Percentage string matching jq's `pct`: round(value*1000)/10 + "%". */
export function pct(value) {
  const v = Math.round((value || 0) * 1000) / 10;
  return Number(v).toString() + '%';
}

/** Sanitize a cell value: backslashes -> "\\", newlines -> " / ", pipes -> "\|", null -> "".
 *  Backslashes are escaped first so a trailing "\" cannot escape the injected "\|". */
export function sanitize(value) {
  const s = (value == null ? '' : String(value));
  return s.replace(/\\/g, '\\\\').replace(/\r?\n/g, ' / ').replace(/\|/g, '\\|');
}

/** Truncate a sanitized cell to `limit`, appending "..." when truncated. */
export function truncateCell(value, limit) {
  const clean = sanitize(value);
  if (clean.length > limit) return clean.slice(0, limit - 3) + '...';
  return clean;
}

/** Render an array as a joined, truncated cell, or "—" for empty/non-arrays. */
export function listOrDash(items, limit) {
  if (Array.isArray(items) && items.length > 0) return truncateCell(items.join(', '), limit);
  return '—';
}

/** Normalize a value into a list of trimmed non-empty strings. */
export function normalizeStringList(value) {
  if (!Array.isArray(value)) return [];
  const out = [];
  for (const item of value) {
    if (typeof item === 'string') {
      const cleaned = item.trim();
      if (cleaned) out.push(cleaned);
    }
  }
  return out;
}

/** Standard GitHub API request headers. */
export function githubHeaders(token) {
  const h = {
    Accept: 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28',
    'User-Agent': 'multi-agent-sdlc-crew-benchmark-slot-gate',
  };
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

/** Parse a Retry-After header (integer seconds or HTTP-date). null on failure. */
export function parseRetryAfter(value) {
  if (!value) return null;
  const candidate = String(value).trim();
  if (!candidate) return null;
  const asInt = Number.parseInt(candidate, 10);
  if (Number.isInteger(asInt) && /^-?\d+$/.test(candidate)) return Math.max(0, asInt);
  const when = new Date(candidate);
  if (Number.isNaN(when.getTime())) return null;
  const delta = (when.getTime() - Date.now()) / 1000;
  return Math.max(0, Math.floor(delta));
}

/** Read a YAML-ish frontmatter field from a markdown file. null if absent. */
export function frontmatterField(path, field) {
  const text = readFileSync(path, 'utf-8');
  if (!text.startsWith('---\n')) return null;
  const re = new RegExp(`^${escapeRegex(field)}:\\s*(.+)$`, 'm');
  const m = text.match(re);
  if (!m) return null;
  return m[1].trim();
}

function escapeRegex(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/** Spawn a process with an explicit argv (never a shell string). */
export function runSync(cmd, argv, opts = {}) {
  return spawnSync(cmd, argv, { encoding: 'utf-8', ...opts });
}