# Security Policy

## Supported versions

Only the latest `main` branch of this repository is supported with security fixes.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security problems.

Email the maintainer directly, or use GitHub's private vulnerability reporting
("Report a vulnerability" under the Security tab). Include:

- a description of the issue and its impact
- steps to reproduce
- the affected file or hook path, if known

You should receive an initial response within 72 hours. Please allow reasonable
time for a fix before public disclosure.

## Scope

This project is a Claude Code **configuration profile** (hooks, agents, settings).
Security-relevant issues include:

- hook bypasses that allow a blocked dangerous command to execute
- permission `deny` rules that can be circumvented
- secret/credential leakage in committed files
- hook scripts that write sensitive data to world-readable logs

Out of scope: the behavior of the Claude Code runtime itself, and any model or
third-party provider routed through the profile.

## Hardening defaults

The profile ships defense-in-depth controls; see [`docs/architecture.md`](docs/architecture.md)
and [`docs/token-cost.md`](docs/token-cost.md) for how they fit together:

- `permissions.deny` blocks `sudo`, `mkfs`, `dd`, `rm -rf /`, `rm -rf ~`,
  `git push --force`, and reads of `.env*`, `secrets/**`, `credentials/**`
- `PreToolUse` / `PermissionRequest` hooks block dangerous and out-of-scope commands
- release/deploy automation is intentionally disabled
- hook JSONL logs rotate past 1 MB to bound growth
- an optional local pre-push secret-scan hook can be installed per-repo with
  `bash scripts/install-git-hooks.sh` (the authoritative scan is TruffleHog in CI)