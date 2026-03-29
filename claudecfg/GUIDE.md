# Claude Code — Cheatsheet

## Model
- Current default: `minimax-m2.5:cloud`

## Navigation
- `Read path/to/file` — read file
- `Grep "pattern"` — search in code
- `Glob "**/*.py"` — find files

## Planning
- `EnterPlanMode` — for tasks >2-3 files
- `TaskCreate` — create task
- `TaskList` — list tasks

## Git
- **Never** `git reset --hard`, `git push --force` without asking
- Always show `git status` + `git diff` before commit

## Important
- Don't delete files without asking
- Don't change configs automatically
- Don't commit myself
- Don't touch .env, secrets, credentials
- No release/deploy automation in this profile

## Slash Commands

These commands invoke specialized agents:
The hooks enforce the actual handoff and stop gates; the commands below are the documented entry points.

### General
- `/manager` — planning and coordination session (invokes @manager)
- `/explore` — codebase exploration session (invokes @explorer)
- `/bug` — bug-hunting session (invokes @bugbuster)
- `/debug` — debugging session
- `/test` — testing session (invokes @tester)
- `/design` — design session (invokes @architect)
- `/refactor` — refactoring session (invokes @housekeeper)
- `/review` — code review (invokes @code-reviewer)
- `/docs` — documentation session (invokes @docwriter)

## Subagents (shortcuts)

| Alias | Agent | Purpose |
|-------|-------|---------|
| `@m` | Manager | Coordinates other agents |
| `@cr` | Code Reviewer | Code review + security |
| `@t` | Tester | Writing tests (TDD, BDD) |
| `@e` | Explorer | Exploring code |
| `@a` | Architect | System design + SOLID |
| `@bug` | Bugbuster | Bug hunting |
| `@dbg` | Debugger | Debugging issues |
| `@doc` | Docwriter | Documentation |
| `@hk` | Housekeeper | Cleanup + DevOps |

Also works: `@manager`, `@code-reviewer`, etc.

### Slash command examples

```text
/manager plan a bugfix for flaky login tests
/explore trace how auth state is loaded
/bug investigate why payments retry forever
/debug reproduce the cache invalidation issue
/test add regression coverage for password reset
/design design an API for report exports
/refactor clean up duplicated formatting helpers
/review review the authentication changes
/docs update the quickstart after CLI changes
```

## Auto-Execution

When working in a project folder (`~/projects/**`, `~/code/**`, `~/repos/**`, `~/work/**`):
- Commands execute automatically
- No confirmation needed for safe operations
- Security restrictions still apply (no sudo, rm -rf /, etc.)
- Hooks still enforce SDLC gates and block release/deploy actions

Outside project folders, confirmation is required.

## Hook-Gated SDLC

Mandatory flow:

`discover -> design -> implement -> verify -> review -> docs when behavior changes -> cleanup`

Main checkpoints:

- `SessionStart` — bootstrap SDLC context and detect test/lint/build commands
- `UserPromptSubmit` — classify work as feature, bugfix, refactor, review, or docs and seed required subagent roles
- `PreToolUse` / `PermissionRequest` — block dangerous or out-of-scope commands, including force-push, `mkfs*`, and remote bootstrap pipes
- `PostToolUse` / `PostToolUseFailure` — record edits and successful or failed test/lint/build status
- `SubagentStart` / `SubagentStop` — enforce the subagent output contract with shell guards
- `TaskCompleted` / `TeammateIdle` / `Stop` — share the same gate logic and block completion after missing verification, failed test/lint/build runs, or missing required subagent roles
- `SessionEnd` — log transcript path and session metadata for later indexing

`Stop` is shell-enforced by `hooks/stop-guard.sh`, and `SubagentStop` is shell-enforced by `hooks/subagent-stop-guard.sh`. After code or config changes, the final assistant summary must include explicit summary lines for verification status, review outcome or pending review, changed files or `no files changed`, and remaining risks or `none`. If the repo exposes no detectable `test`, `lint`, or `build` command, the stop guard allows completion without deadlock, but the summary must explicitly say verification was not run and why. Feature, bugfix, refactor, review, and docs workflows also require role-specific subagent handoffs before completion, tracked in shared session state with alias normalization such as `@code-reviewer -> cr`. `SubagentStart` normalization also accepts alias/name/subagent-type fields in both snake_case and camelCase before falling back to generic runtime types.

If a later reply in the same session makes no additional changes after earlier code or config edits, keep reporting the actual verification, review status, changed files, and remaining risks instead of switching to a no-change footer.

Required handoffs:
- `feature` -> `@t`, `@cr`, and one of `@e|@a`
- `bugfix` -> `@t`, `@cr`, and one of `@bug|@e|@dbg`
- `refactor` -> `@t`, `@cr`, and one of `@a|@e|@hk`
- `review` -> `@cr`
- `docs` -> `@doc`

Subagent summaries must include outcome, changed files or `no changes`, verification status, and remaining risks or next step.

## Standard Output

All subagents use the same format:

```
╔══════════════════════════════════════════════════════╗
║  TASK: <name>                                        ║
║  STATUS: <pending|in_progress|completed|blocked>     ║
╠══════════════════════════════════════════════════════╣
║  RESULTS:                                             ║
║  - <result 1>                                        ║
║  - <result 2>                                        ║
╠══════════════════════════════════════════════════════╣
║  NEXT:                                                ║
║  - <next step>                                       ║
╚══════════════════════════════════════════════════════╝
```

## CLAUDE.md
Create `./CLAUDE.md` in project — put project context there (max 50 lines).

## Workflows

Predefined workflows:

- `workflows/bugfix.md` — fix a bug
- `workflows/new-feature.md` — implement feature
- `workflows/refactor.md` — refactor code
- `workflows/security-scan.md` — scan for private data (API keys, passwords, tokens)
- `workflows/release.md` — optional manual checklist, not part of the required SDLC path

### Usage

**Get plan only:**
```
@m fix bug in login
```
Manager returns a plan with steps and agents.

**Execution policy:**
- manager coordination is optional
- hooks, not markdown, enforce verification, required subagent roles, and stop conditions
- code review remains a required final gate for implementation work

**Direct agent invocation:**
```
@manager coordinate rollout for auth changes
@explorer analyze auth module
@bugbuster find the bug
@architect design the fix
@docwriter update the user-facing docs
```

## Docs
- https://docs.anthropic.com/en/docs/claude-code/settings
- https://code.claude.com/docs/en/hooks

## Repository Automation

Repository-level checks are separate from the local Claude profile:

- `.github/workflows/validate.yml` — structural validation on every push and PR
- `.github/workflows/hooks-test.yml` — deterministic hook behavior tests on every push and PR
- `.github/workflows/behavior-benchmark.yml` — behavioral acceptance tasks using the real Claude Code CLI inside benchmark fixtures
- `.github/workflows/security-scan.yml` — repository secret scan on every push and PR, plus weekly schedule

Benchmark support files:

- `tests/hooks/` — hook fixtures and assertions
- `bench/tasks/` — benchmark task definitions
- `bench/fixtures/` — benchmark fixture repositories
- `docs/benchmarking.md` — runner contract and GitHub setup
