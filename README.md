# Claude Code Configuration

[![Repository Checks](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/validate.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/validate.yml)
[![Hook Contracts](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/hooks-test.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/hooks-test.yml)
[![Python Tests](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/python-tests.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/python-tests.yml)
[![Behavior Benchmark Smoke](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/behavior-benchmark.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/behavior-benchmark.yml)
[![Behavior Benchmark Subagents Smoke](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/behavior-benchmark-subagents-smoke.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/behavior-benchmark-subagents-smoke.yml)
[![Security Checks](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/security-scan.yml/badge.svg?branch=main)](https://github.com/C0FFEEC0DE/claude-crew/actions/workflows/security-scan.yml)

Badges reflect the latest workflow result for the `main` branch.

The profile keeps `outputStyle: "Default"` for coding sessions so Claude Code's built-in engineering instructions stay active. Explanatory behavior belongs in agent prompts and docs, not in the global output-style override.

## Quick Start

```bash
./install.sh
```

This will backup your current config and install the new one.

## Auto-Execution

In project folders (`~/projects/**`, `~/code/**`, `~/repos/**`, `~/work/**`), agents can execute safe commands automatically without confirmation.

### Safety
- Protected paths: `~/.ssh`, `~/.aws`, `/etc`, `/usr`, etc.
- Denied commands: `sudo`, `mkfs`, `dd`, `rm -rf /`
- Confirmation required outside project folders
- Release/deploy actions are intentionally out of scope for this profile

## What's Included

### Agents (8)

| Alias | Agent | Character | Purpose |
|-------|-------|-----------|---------|
| `@m` | Manager | Big Boss | Coordinates other agents |
| `@cr` | Code Reviewer | Toxic Senior | Code review + security |
| `@t` | Tester | Paranoid | Verification and regression testing |
| `@e` | Explorer | Nerd | Exploring code |
| `@a` | Architect | The Architect | System design + SOLID |
| `@bug` | Bugbuster | Cyber Detective | Bug hunting |
| `@dbg` | Debugger | Bug Hunter | Debugging issues |
| `@doc` | Docwriter | Wiki-Wiki | Documentation |
Full names also work: `@manager`, `@code-reviewer`, etc.

### Slash Commands

Slash commands that invoke specialized agents. The hooks still enforce the actual handoff and stop gates; these docs describe the intended entry points.

- `/manager` — manager-led orchestration session (invokes @manager)
- `/explore` — codebase exploration session (invokes @explorer)
- `/bug` — bug-hunting session (invokes @bugbuster)
- `/debug` — debugging session
- `/test` — testing session (invokes @tester)
- `/design` — design session (invokes @architect)
- `/refactor` — refactoring session (invokes @architect)
- `/review` — code review (invokes @code-reviewer)
- `/docs` — documentation session (invokes @docwriter)

The bundled slash-command skills also carry YAML frontmatter in `claudecfg/skills/` so each specialist runs in a forked context with narrower `allowed-tools`.

### Workflows

- `workflows/bugfix.md` — fix a bug
- `workflows/new-feature.md` — implement feature
- `workflows/refactor.md` — refactor code
- `workflows/security-scan.md` — scan for private data (API keys, passwords, tokens)
- `workflows/release.md` — optional manual checklist, not part of the mandatory SDLC profile

For `feature`, `bugfix`, `refactor`, `review`, and `docs` work, the profile is now role-enforced before completion. Hooks track canonical subagent aliases in session state, so full names like `@code-reviewer` normalize to `cr`. Manager-led orchestration is tracked separately through `manager_mode=orchestrate`; top-level `@m` use is not treated as a required specialist subagent handoff. For `feature`, `bugfix`, and `refactor`, a recorded successful test command satisfies the tester side of the gate; otherwise `@t` is still required. `SubagentStart` normalization also accepts alias/name/subagent-type fields from both snake_case and camelCase payloads before falling back to generic agent types. If a Claude Code runtime loads slash skills such as `/review` without emitting `SubagentStart`, or records specialist launches only as transcript lines like `Code Reviewer(...)`, the hooks also infer the specialist role from the transcript so manager-led orchestration does not false-block on review/docs/test handoffs.

Required handoffs by workflow:
- `feature` -> successful verification or `@t`, plus `@cr` and one of `@e|@a`
- `bugfix` -> successful verification or `@t`, plus `@cr` and one of `@bug|@e|@dbg`
- `refactor` -> successful verification or `@t`, plus `@cr` and one of `@a|@e`
- `review` -> `@cr`
- `docs` -> `@doc`

Review policy:
- `review` keeps `@cr` as the only enforced gate
- broad multi-file, workflow, or subsystem reviews should normally use `@e` first so `@cr` reviews against a code map instead of doing all discovery inline
- small localized reviews can stay `@cr`-only when the scope is already obvious

### Hooks

The profile uses hooks as enforcement points, not markdown alone:

- `SessionStart` — bootstrap SDLC context and detect test/lint/build commands
- `UserPromptSubmit` — classify task into `bugfix|feature|refactor|review|docs` and seed required subagent roles
- `PreToolUse` / `PermissionRequest` / `PermissionDenied` — block destructive or out-of-scope actions, including force-push, `mkfs*`, and remote bootstrap pipes such as `curl|bash` or `wget|bash`; `PermissionDenied` retries only when the command was not hard-denied by profile policy and the session is not running in benchmark headless mode
- `PostToolUse` / `PostToolUseFailure` — track edits plus successful or failed test/lint/build commands
- `SubagentStart` / `SubagentStop` — enforce the subagent handoff contract through shell hooks instead of prompt hooks
- `TaskCompleted` / `Stop` / `TeammateIdle` — use the shared session state to block completion after missing verification, failed test/lint/build runs, or missing required subagent roles for the current workflow
- `Notification` — log runtime notifications for later debugging and observability
- `SessionEnd` — index transcript paths and session metadata for later dataset work

`Stop` and `SubagentStop` are enforced by shell guards only. This avoids prompt-hook failures on tool-only turns while still requiring structured final summaries after code/config changes or subagent handoffs. If a repo has no detected `test`, `lint`, or `build` command, `Stop` no longer deadlocks the session, but the final summary must explicitly say that verification was not run and why. In manager-led workflows, `TeammateIdle` also blocks if no specialist handoff happened yet, so `@m` cannot linger in manager-only analysis indefinitely. When the runtime explicitly backgrounds a live manager-led workflow and no code/config changes have happened yet, `Stop` now defers the specialist-role gate for that turn instead of looping on a premature finalization attempt.
For code or config changes, the stop-safe summary is line-oriented: include exact summary lines for `Verification status:`, `Review outcome:`, `Changed files:` or `No files changed:`, and `Remaining risks:` rather than relying on loose keywords alone. For subagent handoffs, use `Outcome:`, `Changed files:` or `No files changed:`, `Verification status:`, and one closure line: either `Remaining risks:` or `Next step:`.
General informational questions should remain outside the SDLC workflow gates. Mentions of models, Ollama, or OpenRouter only trigger implementation workflows when the prompt also asks to change the repository, such as adding support, integrating, configuring, or implementing behavior.

If a later reply in the same session makes no additional changes after earlier code/config edits, keep reporting the actual verification, review status, changed files, and remaining risks instead of switching to a no-change footer.


## Usage

### Call an agent directly (shortcuts)
```
@e explore the auth module
@cr review api.py
@t write tests for utils
@a design user auth
@bug find login bug
```

### Use full names
```
@explorer explore the auth module
@code-reviewer review api.py
@tester write tests for utils
```

### Use workflow
```
@m fix bug in login
@manager implement new feature: user authentication
```

Manager owns orchestration by default and keeps the workflow moving until completion or a concrete blocker. Use explicit wording like "plan only" when you want planning without execution. Completion is still enforced by hooks. The expected flow is:
`discover -> design -> implement -> verify -> review -> docs when behavior changes -> cleanup`

Manager may also launch multiple agents of the same role in parallel when their scopes are clearly separated. Completion gates remain role-based; parallel instances are tracked separately for orchestration visibility.

### Use slash command
```
/manager
/explore
/bug
/debug
/test
/design
/refactor
/review
/docs
```

## Configuration

See `claudecfg/settings.json` for permissions and settings. Base permissions stay broad enough for project work, while slash-command skills narrow their own runtime surface through per-skill frontmatter.
The default output style is `Default` to preserve Claude Code's built-in software-engineering instruction stack.

## CI and Claude Code

GitHub Actions now covers six layers:

- `Repository Checks` — fast structural and lint checks on every push and PR
- `Hook Contracts` — behavior tests for the SDLC hook scripts
- `Python Tests` — focused pytest coverage for the benchmark runner and profile metadata
- `Behavior Benchmark Smoke` — fast live Claude Code smoke coverage on PRs when benchmark-relevant files change
- `Behavior Benchmark Subagents Smoke` — per-agent coverage on PRs when benchmark-relevant files change
- `Security Checks` — repository secret and sensitive-file scan

The fast checks run automatically on every push and PR. `Behavior Benchmark Smoke` and `Behavior Benchmark Subagents Smoke` only run on PRs that touch benchmark-relevant files, and they select only the task files impacted by the changed agents, skills, fixtures, hooks, or benchmark infrastructure. That selection is derived from benchmark task metadata plus the frontmatter in `claudecfg/agents/*.md` and `claudecfg/skills/*.md`, so alias files and full-name files stay wired to the same benchmark coverage.

### Fast CI

`Repository Checks` runs:

- `bash scripts/validate.sh`
- shell syntax checks for `claudecfg/hooks/*.sh` and `scripts/*.sh`
- workflow lint with `actionlint`
- shell lint with `shellcheck`
- installer smoke/idempotency check via `tests/install/install-smoke.sh`
- JSON checks for settings, hook cases, hook scenarios, and benchmark metadata
- slash-command inventory checks across `claudecfg/commands/`, `README.md`, `claudecfg/GUIDE.md`, and `claudecfg/README.md`
- `git diff --check`

`Hook Contracts` runs:

- `bash scripts/test-hooks.sh`
- `bash scripts/test-hooks.sh tests/hooks/scenarios.json`

`Python Tests` runs:

- `python -m pytest tests/bench/test_bench_runner.py tests/bench/test_benchmark_task_selection.py tests/bench/test_collect_benchmark_changes.py tests/bench/test_build_benchmark_matrix.py tests/bench/test_wait_for_benchmark_slot.py tests/bench/test_merge_benchmark_summaries.py tests/bench/test_render_benchmark_summary.py tests/test_skills_frontmatter.py -v`
- `python -m pytest tests/test_settings_hooks.py tests/test_hook_scenarios.py -v` remains grouped with `Hook Contracts`, because those tests validate the hook manifests and hook configuration contract directly

This harness verifies that key hooks block dangerous commands, classify prompts correctly, record verification state, reject incomplete stop summaries, and refuse completion after missing or failed verification when code changed.

### Behavior Benchmark Smoke

`.github/workflows/behavior-benchmark.yml` is the behavioral acceptance gate for the profile.

That workflow:

- installs the Claude Code CLI
- runs `./install.sh` to install the repo config into `~/.claude`
- copies each benchmark fixture into an isolated task workdir
- runs the real `claude -p` inside that workdir
- uses the default CI suite under `bench/tasks/smoke/` (if present)
- uses smart task selection, so agent-only changes run only the smoke tasks related to those agents instead of re-running the entire smoke suite
- only runs on PRs when benchmark-relevant files changed, so normal feature pushes do not keep re-running the live smoke suite unnecessarily
- checks that required tasks actually changed files, kept docs/code scope rules, and still pass verification
- requires the final Claude response to include exact stop-safe summary lines for `Verification status:`, `Review outcome:`, `Changed files:` or `No files changed:`, and `Remaining risks:`
- bootstraps `~/.claude`, `~/.claude/state`, and `~/.claude/logs` before live runs so CI does not waste turns recreating missing Claude home-state directories
- can require actual subagent usage through `required_used_agents` and `required_used_agent_groups`, so workflow-combination tests assert real role handoffs instead of brittle markdown headings
- writes a markdown benchmark report with overview and per-task status tables, so the Actions summary shows exactly which tasks ran and why they passed or failed
- reports both configured and executed task counts so fail-fast runs are not mistaken for full-suite coverage
- uploads per-task Claude logs, results, and workspace patches as artifacts
- fails unless every benchmark task passes
- reports recovered-task and summary-repair metrics by default without failing on them
- only turns recovery metrics into a hard gate when explicit GitHub variables or `workflow_dispatch` inputs set recovery limits
- can also fail on forbidden transcript patterns, which are used to catch prompt regressions such as internal hook/footer repair chatter leaking into user-facing output

This is the fast real Claude Code PR gate in the repository.

The per-agent suite lives under `bench/tasks/subagents/smoke/` with focused canary tasks for each canonical specialist role, plus a few extra workflow-shape tasks. Tasks that care about exact handoff shape use transcript regexes; tasks that mainly care about real role activation assert the actual `SubagentStart`/recorded handoff aliases captured in the debug log.

Each benchmark run also writes `bench-output/benchmark-report.md` inside the artifact bundle, with a markdown table for every executed task.

### Behavior Benchmark Subagents Smoke

`.github/workflows/behavior-benchmark-subagents-smoke.yml` runs the subagent coverage suite on PRs and via manual dispatch.

That workflow:

- runs on PRs when benchmark-relevant files changed
- runs `bench/tasks/subagents/smoke/*.json` with focused canary tasks for each canonical specialist role plus a few workflow-shape tasks
- uses smart task selection so a change in one agent only re-runs that role's task unless shared workflow logic changed
- supports manual `workflow_dispatch` for on-demand checks on `main`

Required benchmark model variable:

- `OLLAMA_MODEL=qwen3.5:cloud`
- optional: `BEHAVIOR_BENCHMARK_MAX_OUTPUT_TOKENS=1024`

## Logs

Hook logs are written under `~/.claude/logs/`. Session metadata and transcript paths are indexed in `~/.claude/logs/session-index.jsonl`.

## Docs

- `claudecfg/GUIDE.md` — full cheatsheet
- `docs/agent-contracts.md` — agent contract matrix, golden regression suite, benchmark assertions, and hook-level contract
- `claudecfg/agents/` — agent definitions
- `claudecfg/skills/` — slash skills with YAML frontmatter (`name`, `description`, `agent`, `context`, `disable-model-invocation`, `allowed-tools`, and `paths`)
- `claudecfg/commands/` — slash command definitions
- `claudecfg/skills/` — reusable slash-skill prompts
- `docs/benchmarking.md` — behavioral benchmark runner and workflow

## Uninstall

To restore backup:
```bash
cp -r ~/.claude.backup.XXX/* ~/.claude/
```

Where `XXX` is the backup timestamp.

## License

MIT
