import os
import subprocess
from pathlib import Path


def run_make_dry_run(*args: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["OLLAMA_API_KEY"] = "must-not-be-used-by-local-default"
    env.pop("OLLAMA_MODEL", None)
    env.pop("BENCH_ANTHROPIC_BASE_URL", None)
    env.pop("BENCH_ANTHROPIC_AUTH_TOKEN", None)
    env.pop("BENCH_ANTHROPIC_API_KEY", None)
    result = subprocess.run(
        ["make", "-n", *args],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_bench_smoke_defaults_to_local_ollama_without_auth():
    output = run_make_dry_run("bench-smoke")

    assert "ANTHROPIC_BASE_URL='http://127.0.0.1:11434'" in output
    assert "ANTHROPIC_AUTH_TOKEN=''" in output
    assert "ANTHROPIC_API_KEY=''" in output
    # No model is pinned by default; the profile is model-agnostic.
    assert "OLLAMA_MODEL=''" in output
    assert "must-not-be-used-by-local-default" not in output


def test_bench_smoke_allows_hosted_ollama_override():
    output = run_make_dry_run(
        "bench-smoke",
        "BENCH_ANTHROPIC_BASE_URL=https://ollama.com",
        "BENCH_ANTHROPIC_AUTH_TOKEN=test-token",
        "OLLAMA_MODEL=example-model",
    )

    assert "ANTHROPIC_BASE_URL='https://ollama.com'" in output
    assert "ANTHROPIC_AUTH_TOKEN='test-token'" in output
    assert "OLLAMA_MODEL='example-model'" in output
