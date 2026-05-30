#!/usr/bin/env python3

import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request


REPO_ROOT = pathlib.Path(os.environ["BENCH_REPO_ROOT"]).resolve()
TASK_FILE = pathlib.Path(os.environ["BENCH_TASK_FILE"]).resolve()
WORKDIR = pathlib.Path(os.environ["BENCH_WORKDIR"]).resolve()
OUTPUT_DIR = pathlib.Path(os.environ["BENCH_OUTPUT_DIR"]).resolve()


def env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name, "")
    value = value.strip()
    return value or default


OPENROUTER_API_KEY = os.environ["OPENROUTER_API_KEY"].strip()
OPENROUTER_MODEL = env_or_default("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.5")
OPENROUTER_BASE_URL = env_or_default(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions"
)
OPENROUTER_SITE_URL = env_or_default("OPENROUTER_SITE_URL", "https://github.com")
OPENROUTER_APP_NAME = env_or_default("OPENROUTER_APP_NAME", "claude-crew-benchmark")


def is_docs_path(path_str: str) -> bool:
    path_lower = path_str.lower()
    name = pathlib.Path(path_lower).name
    return (
        path_lower.endswith((".md", ".mdx", ".txt", ".rst", ".adoc", ".markdown"))
        or "/docs/" in path_lower
        or name.startswith("readme")
        or name.startswith("changelog")
        or name == "claude.md"
    )


def read_text_if_exists(path: pathlib.Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def collect_fixture_files(root: pathlib.Path) -> list[dict]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        files.append(
            {
                "path": rel,
                "content": path.read_text(encoding="utf-8"),
            }
        )
    return files


def build_prompt(task: dict, fixture_files: list[dict], claude_md: str, guide_md: str) -> list[dict]:
    task_json = json.dumps(task, ensure_ascii=False, indent=2)
    files_json = json.dumps(fixture_files, ensure_ascii=False, indent=2)
    system_prompt = (
        "You are a one-shot benchmark coding worker. "
        "You receive a small codebase fixture and a task. "
        "Follow the repository guidance below, but do not invent tool execution or hidden automation. "
        "Do not mention release or deploy. "
        "Respond with JSON only using this schema: "
        "{\"summary\": string, \"review_status\": string, \"verification_notes\": string, "
        "\"files\": [{\"path\": string, \"content\": string}], \"notes\": string}. "
        "Return full file contents for each file you want to overwrite. Paths must be relative and stay inside the fixture."
    )
    user_prompt = (
        "Repository guidance from CLAUDE.md:\n"
        f"{claude_md}\n\n"
        "Additional guidance from claudecfg/GUIDE.md:\n"
        f"{guide_md}\n\n"
        "Benchmark task:\n"
        f"{task_json}\n\n"
        "Current fixture files:\n"
        f"{files_json}\n\n"
        "Output JSON only."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def call_openrouter(messages: list[dict]) -> str:
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0,
    }
    request = urllib.request.Request(
        OPENROUTER_BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": OPENROUTER_SITE_URL,
            "X-Title": OPENROUTER_APP_NAME,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenRouter HTTP error {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenRouter request failed: {exc}") from exc

    content = body["choices"][0]["message"]["content"]
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts)
    return content


def extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


def snapshot_files(root: pathlib.Path) -> dict[str, str]:
    snapshot = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            snapshot[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8")
    return snapshot


def apply_files(files: list[dict]) -> None:
    for file_entry in files:
        rel = pathlib.PurePosixPath(file_entry["path"])
        if rel.is_absolute() or ".." in rel.parts:
            raise RuntimeError(f"Unsafe output path from model: {file_entry['path']}")
        target = (WORKDIR / rel.as_posix()).resolve()
        if not str(target).startswith(str(WORKDIR)):
            raise RuntimeError(f"Path escaped workdir: {file_entry['path']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file_entry["content"], encoding="utf-8")


def run_verification() -> tuple[bool, str]:
    tests_exist = any(WORKDIR.glob("test_*.py")) or any(WORKDIR.glob("tests/*.py"))
    if not tests_exist:
        return False, "No Python test files were found in the fixture."

    command = [sys.executable, "-m", "pytest", "-q"]
    completed = subprocess.run(
        command,
        cwd=WORKDIR,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = (completed.stdout + "\n" + completed.stderr).strip()
    return completed.returncode == 0, output


def main() -> int:
    task = json.loads(TASK_FILE.read_text(encoding="utf-8"))
    fixture_files = collect_fixture_files(WORKDIR)
    before = snapshot_files(WORKDIR)

    claude_md = read_text_if_exists(REPO_ROOT / "CLAUDE.md")
    guide_md = read_text_if_exists(REPO_ROOT / "claudecfg" / "GUIDE.md")

    raw_response = call_openrouter(build_prompt(task, fixture_files, claude_md, guide_md))
    model_result = extract_json(raw_response)
    apply_files(model_result.get("files", []))

    after = snapshot_files(WORKDIR)
    changed_files = sorted(
        path for path in set(before) | set(after) if before.get(path) != after.get(path)
    )
    docs_updated = any(is_docs_path(path) for path in changed_files)
    completed = len(changed_files) > 0

    verification_required = bool(task["verification_required"])
    tests_run = False
    tests_passed = False
    verification_log = model_result.get("verification_notes", "").strip()
    if verification_required:
        tests_run = True
        tests_passed, verification_output = run_verification()
        verification_log = (
            verification_log + "\n\n" + verification_output if verification_log else verification_output
        )

    review_required = bool(task["review_required"])
    review_status = model_result.get("review_status", "").strip()
    review_present = bool(review_status)

    docs_required = bool(task["docs_required"])
    status = "passed"
    if not completed:
        status = "failed"
    if verification_required and not tests_passed:
        status = "failed"
    if review_required and not review_present:
        status = "failed"
    if docs_required and not docs_updated:
        status = "failed"

    result = {
        "task_id": task["id"],
        "status": status,
        "completed": completed,
        "verification_required": verification_required,
        "tests_run": tests_run,
        "tests_passed": tests_passed,
        "review_required": review_required,
        "review_present": review_present,
        "docs_required": docs_required,
        "docs_updated": docs_updated,
        "policy_violations": 0,
        "tool_failures": 0 if status == "passed" else 1,
        "runtime_seconds": 0,
        "notes": (
            f"OpenRouter model={OPENROUTER_MODEL}. "
            f"Summary: {model_result.get('summary', '').strip()} "
            f"Review: {review_status or 'missing'}. "
            f"Changed files: {', '.join(changed_files) if changed_files else 'none'}. "
            f"Verification: {verification_log[:800]}"
        ).strip(),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
