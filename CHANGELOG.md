# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added
- `PermissionDenied` hook support so auto-mode classifier denials can retry through the normal approval path when the command is not hard-denied by profile policy
- Auto-execution configuration for project folders (`~/projects/**`, `~/code/**`, `~/repos/**`, `~/work/**`)
- Extended Bash permissions for common dev tools (rm, mkdir, cp, mv, cargo, go, etc.)
- `@debugger` agent for debugging sessions
- `/docs` skill command for documentation
- `skills/` folder for skill definitions
- GitHub Actions security-scan workflow
- CONTRIBUTING.md guidelines
- LICENSE file (MIT)
- Hook-based SDLC gate layer for session start, prompt classification, verification tracking, stop control, and transcript indexing
- Repository-level `Validate` and `Hook Tests` GitHub Actions workflows
- Behavior Benchmark workflow that runs the real Claude Code CLI inside isolated benchmark fixtures and uploads per-task artifacts
- OpenRouter-backed Claude Code benchmark setup documentation
- Behavioral benchmark documentation and summary gate script
- README status badges for repository workflows

### Changed
- Behavior Benchmark recovery metrics now remain visible in `summary.json` and the GitHub summary without failing CI by default; strict recovery caps only apply when explicitly set through GitHub variables or `workflow_dispatch`
- Benchmark transcript regression coverage now includes a reusable forbidden meta-chatter pattern set and limits forbidden transcript scans to assistant-like entries so user prompts do not trigger false positives
- Golden subagent regression coverage is now explicit: every canonical agent alias must have at least one focused benchmark task with `agent_alias` plus non-empty required/forbidden transcript assertions, and the contract is documented in `docs/agent-contracts.md`
- `PermissionDenied` retry behavior now disables retries in benchmark headless runs so denied shell commands do not consume turn budget during automated benchmark tasks
- Tightened prompt classification so benchmark `Workflow override` and `workflow_category` markers take priority over keyword heuristics, preventing `fixture`/similar text from misclassifying refactor tasks as bugfix work
- Moved the canonical installer entrypoint to repository root `./install.sh` and kept `claudecfg/install.sh` as a compatibility wrapper
- Fixed agent types to use specialized types instead of `general-purpose`
- Reworked workflows around hook-gated execution instead of manager auto-execution promises
- Moved release/deploy out of the default profile into an optional manual checklist
- Updated docs to reflect implemented commands only
- Updated GUIDE.md with new agents and skills
- Updated GitHub Actions workflows to run on every push
- Replaced the custom benchmark coding-agent workflow with automatic real Claude Code CLI runs via OpenRouter
- Removed the standalone `Real Claude Code` smoke workflow so `Behavior Benchmark` is now the only real-agent GitHub workflow
- Tightened hook safety and completion gates: expanded dangerous-command blocking, unified failed test/lint/build gating, and moved `Stop` enforcement fully into shell hooks to avoid tool-only prompt-hook failures
- Moved `SubagentStop` enforcement into a shell hook so subagent stop validation no longer depends on prompt-hook message availability
- Updated shell stop gating so repos without detectable `test`/`lint`/`build` commands do not deadlock completion after config changes
- Added role-based subagent enforcement for `feature`, `bugfix`, `refactor`, `review`, and `docs` workflows before completion, with alias normalization and workflow-specific required roles
- Extended `SubagentStart` normalization to prefer alias, name, and subagent-type fields from snake_case and camelCase payloads before generic runtime types
- Updated workflow context and stop feedback with a stop-safe no-op footer for later replies in already dirty sessions
- Switched manager-led workflow enforcement to track manager activation via `manager_mode` instead of incorrectly requiring `@m` as a specialist subagent handoff
- Added an early-specialist-handoff guard so manager-led workflows cannot go idle before delegating to at least one specialist role
- Reworked benchmark automation so the main acceptance path now uses the real Claude Code CLI instead of a one-shot OpenRouter worker
- Improved GitHub Actions observability with readable Claude diagnostics in workflow logs, step summaries, and benchmark task artifacts
- Expanded `Behavior Benchmark` live logs with per-task metadata, prompt excerpts, raw Claude JSON excerpts, patch excerpts, and structured result dumps
- Added per-task `claude-debug.log` capture for the live benchmark path so empty-result failures can be debugged from Claude CLI traces
- Updated the live benchmark runner to use `--permission-mode acceptEdits` and surface `subtype`, `stop_reason`, and permission-denial diagnostics in task results
- Increased the default `Behavior Benchmark` turn budget from `8` to `12` per task
- Added an explicit workflow override to benchmark prompts so implementation tasks are not misclassified as `review` by hook-driven prompt classification
- Switched the default OpenRouter model for the live Claude Code benchmark path to `nvidia/nemotron-3-super-120b-a12b:free`
- Taught `Stop` and `SubagentStop` shell guards to recover the last assistant summary from `transcript_path` when live runtime payloads omit `last_assistant_message`
- Taught the live benchmark runner to recover final summaries from the session transcript when Claude returns an empty `.result` payload after otherwise-valid work
- Enabled fail-fast and a wall-clock timeout in `Behavior Benchmark` so CI stops quickly after the first failed task instead of burning the full task set
- Increased the default `Behavior Benchmark` turn budget from `12` to `16` per task
- Increased the live benchmark task timeout from `180` to `300` seconds so slower OpenRouter-backed models can finish after successful edits and verification
- Updated the benchmark harness to copy the repository `.claude/` directory into each fixture workdir so project-local Claude settings are exercised during live behavioral runs
- Allowed root-level `Read`, `Glob`, and `Grep` in Claude settings so live benchmark agents can inspect `.` without avoidable permission denials
- Made the `bugfix-zero-division` benchmark contract explicitly require a `README.md` update so docs compliance is unambiguous for the first bugfix gate
- Added task-level `forbidden_doc_patterns` support to the benchmark runner so docs tasks can fail on hallucinated files, commands, or clone steps in generated README changes
- Tightened `docs-quickstart-clarity` to forbid invented files or install steps such as `requirements.txt`, `generate_report.py`, `git clone`, and `pip install -r`
- Updated review guidance so broad workflow, subsystem, and multi-file reviews should normally map the area with `@explorer` before `@code-reviewer`, while keeping `@cr` as the only enforced review gate

### Fixed
- New Feature workflow missing implementation and test steps
- Missing post-implementation code review in workflows
- `make lint` is now tracked as lint instead of build in hook session state
- `Stop`/`TaskCompleted`/`TeammateIdle` now consistently block after failed verification commands
- Added regression coverage for force-push, `mkfs*`, remote bootstrap pipes, tool-only stop turns, and incomplete final summaries
- Added shell-based regression coverage for incomplete subagent summaries and missing subagent assistant messages
- Fixed false `@general-purpose` role recording when specialized subagents were invoked through generic runtime payload fields
- Reduced stop-loop UX friction by surfacing a ready-to-use no-change footer in stop-guard feedback
- Fixed live `SubagentStop` and `Stop` false blocks caused by missing `last_assistant_message` in runtime hook payloads despite valid assistant summaries in the session transcript
- Fixed false review gating when runtimes recorded specialist launches only in transcript lines such as `Skill(/review)` or `Code Reviewer(...)`
- Fixed stop-loop false blocks when manager-led workflows were backgrounded before the first specialist handoff completed

## [1.0.0] - 2026-03-19

### Added
- Initial release with 8 agents
- 10 slash commands
- 5 workflows
- Manager agent with execution planning
- Security-scan workflow documentation
