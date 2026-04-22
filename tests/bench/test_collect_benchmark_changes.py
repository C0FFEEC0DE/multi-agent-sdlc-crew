import os
import subprocess
from pathlib import Path


def run(cmd, cwd, env=None):
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd,
        cwd=cwd,
        env=merged_env,
        check=True,
        text=True,
        capture_output=True,
    )


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def setup_git_identity(repo: Path) -> None:
    env = {
        "GIT_AUTHOR_NAME": "Test User",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test User",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    run(["git", "config", "user.name", env["GIT_AUTHOR_NAME"]], cwd=repo)
    run(["git", "config", "user.email", env["GIT_AUTHOR_EMAIL"]], cwd=repo)


def test_workflow_dispatch_on_feature_branch_collects_diff_vs_base(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "collect-benchmark-changes.sh"
    origin = tmp_path / "origin.git"
    worktree = tmp_path / "worktree"

    run(["git", "init", "--bare", str(origin)], cwd=tmp_path)
    run(["git", "clone", str(origin), str(worktree)], cwd=tmp_path)
    setup_git_identity(worktree)

    run(["git", "switch", "-c", "main"], cwd=worktree)
    write_file(worktree / "README.md", "seed\n")
    run(["git", "add", "README.md"], cwd=worktree)
    run(["git", "commit", "-m", "seed"], cwd=worktree)
    run(["git", "push", "-u", "origin", "main"], cwd=worktree)

    run(["git", "switch", "-c", "feature"], cwd=worktree)
    write_file(worktree / "claudecfg" / "agents" / "manager.md", "changed\n")
    run(["git", "add", "claudecfg/agents/manager.md"], cwd=worktree)
    run(["git", "commit", "-m", "feature change"], cwd=worktree)

    output_path = tmp_path / "feature-changes.txt"
    run(
        [
            "bash",
            str(script_path),
            "--event",
            "workflow_dispatch",
            "--output",
            str(output_path),
            "--base-ref",
            "main",
            "--ref-name",
            "feature",
        ],
        cwd=worktree,
    )

    assert output_path.read_text(encoding="utf-8").splitlines() == ["claudecfg/agents/manager.md"]


def test_workflow_dispatch_on_main_collects_recent_history(tmp_path):
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "collect-benchmark-changes.sh"
    origin = tmp_path / "origin.git"
    worktree = tmp_path / "worktree"

    run(["git", "init", "--bare", str(origin)], cwd=tmp_path)
    run(["git", "clone", str(origin), str(worktree)], cwd=tmp_path)
    setup_git_identity(worktree)

    run(["git", "switch", "-c", "main"], cwd=worktree)
    write_file(worktree / "README.md", "seed\n")
    run(["git", "add", "README.md"], cwd=worktree)
    run(["git", "commit", "-m", "seed"], cwd=worktree)
    run(["git", "push", "-u", "origin", "main"], cwd=worktree)

    write_file(worktree / "bench" / "fixtures" / "node-app" / "README.md", "recent change\n")
    run(["git", "add", "bench/fixtures/node-app/README.md"], cwd=worktree)
    run(["git", "commit", "-m", "recent main change"], cwd=worktree)

    output_path = tmp_path / "main-changes.txt"
    run(
        [
            "bash",
            str(script_path),
            "--event",
            "workflow_dispatch",
            "--output",
            str(output_path),
            "--base-ref",
            "main",
            "--ref-name",
            "main",
        ],
        cwd=worktree,
    )

    # Files are collected and sorted with sort -u; order is locale-dependent.
    assert set(output_path.read_text(encoding="utf-8").splitlines()) == {"README.md", "bench/fixtures/node-app/README.md"}
