import importlib.util
import json
from pathlib import Path


def load_selector_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "select-benchmark-tasks.py"
    spec = importlib.util.spec_from_file_location("select_benchmark_tasks", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def select_ids(
    module,
    suite,
    changed_files,
    selection_mode="changed",
    previous_summary=None,
    exclude_overlap_with_suite=None,
    priority_profile=None,
    max_tasks=None,
):
    tasks = module.iter_tasks()
    selected, reasons = module.select_tasks(
        tasks,
        suite,
        changed_files,
        selection_mode,
        previous_summary=previous_summary,
        exclude_overlap_with_suites=[exclude_overlap_with_suite] if exclude_overlap_with_suite else [],
    )
    selected = module.apply_priority_profile(selected, priority_profile)
    selected = module.limit_tasks(selected, max_tasks, reasons)
    return {task["id"] for task in selected}, reasons


def test_subagent_smoke_agent_change_selects_only_that_role():
    """Agent file change selects only tasks for that agent role."""
    selector = load_selector_module()
    selected_ids, reasons = select_ids(
        selector,
        "subagents_smoke",
        ["claudecfg/skills/review.md"],
    )

    assert "agent_or_skill_change" in reasons
    assert selected_ids == {"subagent-code-reviewer-note-lite"}


def test_full_name_skill_mapping_selects_related_subagent_smoke_task():
    """Skill file change selects related subagent smoke tasks."""
    selector = load_selector_module()
    selected_ids, reasons = select_ids(
        selector,
        "subagents_smoke",
        ["claudecfg/skills/docs.md"],
    )

    assert "agent_or_skill_change" in reasons
    assert selected_ids == {
        "subagent-architect-rollout-lite",
        "subagent-docwriter-quickstart-lite",
    }


def test_impacted_agents_returns_alias_for_agent_file():
    """Agent file change returns correct alias."""
    selector = load_selector_module()
    result = selector.impacted_agents(["claudecfg/agents/bug.md"])
    assert "bug" in result


def test_impacted_agents_returns_alias_for_skill_file():
    """Skill file change returns correct alias."""
    selector = load_selector_module()
    result = selector.impacted_agents(["claudecfg/skills/review.md"])
    assert "cr" in result


def test_impacted_agents_handles_multiple_changed_files():
    """Multiple file changes return correct aliases."""
    selector = load_selector_module()
    result = selector.impacted_agents([
        "claudecfg/agents/docwriter.md",
        "claudecfg/agents/architect.md",
    ])
    assert "doc" in result
    assert "a" in result


def test_impacted_agents_ignores_unrelated_files():
    """Unrelated files return empty set."""
    selector = load_selector_module()
    result = selector.impacted_agents(["README.md", ".github/workflows/ci.yml"])
    assert result == set()


def test_changed_task_paths_filters_task_paths():
    """Only task paths are returned."""
    selector = load_selector_module()
    result = selector.changed_task_paths([
        "README.md",
        "bench/tasks/subagents/smoke/test-task.json",
        "scripts/helper.sh",
    ])
    assert result == {"bench/tasks/subagents/smoke/test-task.json"}


def test_changed_task_paths_empty_input():
    """Empty input returns empty set."""
    selector = load_selector_module()
    assert selector.changed_task_paths([]) == set()


def test_dedupe_tasks_removes_duplicates():
    """Duplicate tasks are removed."""
    selector = load_selector_module()
    task_a = {"id": "task-a", "_path": "bench/tasks/subagents/smoke/a.json"}
    task_b = {"id": "task-b", "_path": "bench/tasks/subagents/smoke/b.json"}
    task_a_dup = {"id": "task-a", "_path": "bench/tasks/subagents/smoke/a.json"}
    result = selector.dedupe_tasks([task_a, task_b, task_a_dup])
    assert len(result) == 2
    assert {t["id"] for t in result} == {"task-a", "task-b"}


def test_docs_tasks_have_minimal_fixture_readmes():
    """
    Validate that docs_required tasks have fixtures where README.md needs updating.
    This catches task/fixture misalignment where fixture already has quickstart content.
    """
    repo_root = Path(__file__).resolve().parents[2]

    # Quickstart content patterns that indicate fixture already has docs
    quickstart_patterns = [
        "npm test",
        "pytest -q",
        "quickstart",
        "## Usage",
        "## Getting Started",
    ]

    # Check all docs_required tasks
    for task_path in repo_root.glob("bench/tasks/**/*.json"):
        task = json.loads(task_path.read_text(encoding="utf-8"))

        if not task.get("docs_required", False):
            continue

        fixture_name = task.get("fixture")
        if not fixture_name:
            continue

        fixture_readme = repo_root / "bench" / "fixtures" / fixture_name / "README.md"
        if not fixture_readme.exists():
            continue

        readme_content = fixture_readme.read_text(encoding="utf-8")

        # Task ID for error messages
        task_id = task.get("id", str(task_path))

        # Check if fixture README already has quickstart content
        for pattern in quickstart_patterns:
            if pattern.lower() in readme_content.lower():
                # Allow if task explicitly references existing content
                prompt = task.get("prompt", "")
                if pattern.lower() in prompt.lower():
                    continue

                # Check if this is a quickstart addition task
                if "quickstart" in prompt.lower() or "npm test" in prompt.lower():
                    raise AssertionError(
                        f"Task/fixture misalignment: {task_id}\n"
                        f"Task requires docs update but fixture README already contains '{pattern}'\n"
                        f"Fixture: {fixture_readme}\n"
                        f"Fix: Reset fixture README to minimal state or change task"
                    )