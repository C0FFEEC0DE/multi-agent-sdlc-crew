# Claude Code Configuration

## Directory Structure

### `claudecfg/`

Source configuration directory. Contains:

- `settings.json` — Claude Code main settings
- `hooks/` — hook scripts for SDLC gates and session logging
- `agents/` — agent definitions
- `commands/` — slash command definitions
- `workflows/` — workflow definitions
- `skills/` — skill definitions
- `install.sh` — compatibility wrapper to the repository-level installer
- `GUIDE.md` — complete guide

Repository-level CI and benchmarking live under `.github/workflows/`, `scripts/`, `tests/hooks/`, and `bench/`.

The repository validator also checks that the bundled slash-command file inventory and the published slash-command lists stay in sync.

Current bundled slash commands:

These are the documented entry points for the configured agents; hook enforcement still applies at runtime.

- `/manager`
- `/explore`
- `/bug`
- `/debug`
- `/test`
- `/design`
- `/refactor`
- `/review`
- `/docs`

### `.claude/`

Target Claude Code directory (`$HOME/.claude/`). Files are copied here during installation. Hook logs are stored under `$HOME/.claude/logs/`.

## Installation

```bash
# from repository root
./install.sh
```

The repository-level script:
1. Creates backup of current `~/.claude/` directory
2. Creates `~/.claude/` if missing
3. Copies all files from `claudecfg/` to `~/.claude/`
4. Ensures hook scripts are executable
5. Verifies installation

## Purpose

- `claudecfg/` — tracked source of truth
- `~/.claude/` — Claude Code working directory
- `$HOME/.claude/logs/` — hook logs and transcript index
- repository root — GitHub Actions, hook test harness, and benchmark fixtures
