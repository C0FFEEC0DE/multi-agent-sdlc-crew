# claude-crew

[![Repository Checks](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/validate.yml)
[![Hook Contracts](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/hooks-test.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/hooks-test.yml)
[![Python Tests](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/python-tests.yml)
[![Security Checks](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/security-scan.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/security-scan.yml)

Hook-gated SDLC profile for Claude Code with 8 specialist agents.

## Install

```bash
./install.sh
```

Backs up your current `~/.claude` config and installs this one.

## Agents

| Alias | Role | Purpose |
|-------|------|---------|
| `@m` | Manager | Orchestrates other agents |
| `@cr` | Code Reviewer | Code review + security |
| `@t` | Tester | Verification + regression |
| `@e` | Explorer | Codebase exploration |
| `@a` | Architect | System design |
| `@bug` | Bugbuster | Bug hunting |
| `@dbg` | Debugger | Debugging issues |
| `@doc` | Docwriter | Documentation |

Full names work too: `@code-reviewer`, `@tester`, etc.

## Usage

```
@e explore the auth module
@cr review api.py
@t write tests for utils
@manager implement new feature: user authentication
```

### Slash Commands

- `/manager` — manager-led orchestration session (invokes @manager)
- `/explore` — codebase exploration session (invokes @explorer)
- `/bug` — bug-hunting session (invokes @bugbuster)
- `/debug` — debugging session
- `/test` — testing session (invokes @tester)
- `/design` — design session (invokes @architect)
- `/refactor` — refactoring session (invokes @architect)
- `/review` — code review (invokes @code-reviewer)
- `/docs` — documentation session (invokes @docwriter)

### Workflows

Slash commands are the documented entry points; the hooks enforce the actual handoff and stop gates (see `## Workflow`).

## Workflow

The hooks enforce this flow for code changes:

```
discover -> design -> implement -> verify -> review -> docs -> cleanup
```

Runtime `Notification` events are logged to `notification.jsonl` for observability.

Required handoffs:

| Type | Required |
|------|----------|
| feature | `@t` or verification + `@cr` + `@e` or `@a` |
| bugfix | `@t` or verification + `@cr` + `@bug`, `@e`, or `@dbg` |
| refactor | `@t` or verification + `@cr` + `@a` or `@e` |
| review | `@cr` |
| docs | `@doc` |

## Safety

- Protected paths: `~/.ssh`, `~/.aws`, `/etc`, `/usr`
- Blocked: `mkfs`, `dd`, `rm -rf /`, force-push, remote bootstrap pipes
- Auto-execution only in project folders (`~/projects/**`, `~/code/**`, `~/repos/**`, `~/work/**`)

## Docs

- `claudecfg/GUIDE.md` — quick reference
- `docs/benchmarking.md` — benchmark setup
- `docs/agent-contracts.md` — agent contracts
- `claudecfg/agents/` — agent definitions
- `claudecfg/skills/` — slash skills

## License

MIT
