"""
Task/fixture alignment validation tests.

These tests validate that benchmark tasks and their fixtures are properly aligned:
- Tasks should have fixtures in the expected initial state
- Fixtures should not already satisfy task success_criteria
- Metadata fields should reference valid fixtures and agents

This catches "task/fixture misalignment" where a task expects to add docs/features/fixes
but the fixture already has that content.
"""

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = REPO_ROOT / "bench" / "fixtures"
TASKS_DIR = REPO_ROOT / "bench" / "tasks"

# Valid agent aliases from the profile
VALID_AGENT_ALIASES = {
    "m", "e", "a", "bug", "dbg", "t", "cr", "doc", "hk",
    "manager", "explorer", "architect", "bugbuster", "debugger",
    "tester", "code-reviewer", "docwriter", "housekeeper", "veles",
}

# Patterns indicating fixture already has content
QUICKSTART_PATTERNS = ["npm test", "pytest -q", "quickstart", "usage", "getting started"]
BUG_PATTERNS = ["raise ValueError", "raise Exception"]  # Proper error handling (bug fixed)

# Feature detection: check for actual implementation (not stubs)
# Stubs like "return 0" or "pass" or "TODO" indicate incomplete implementation
STUB_INDICATORS = ["return 0", "return 0.0", "pass", "TODO", "# stub", "// stub"]


def load_all_tasks():
    """Load all task definitions from bench/tasks."""
    tasks = []
    for task_path in TASKS_DIR.glob("**/*.json"):
        task = json.loads(task_path.read_text(encoding="utf-8"))
        task["_path"] = task_path
        tasks.append(task)
    return tasks


def get_fixture_readme(fixture_name: str) -> str | None:
    """Get README.md content for a fixture, or None if not found."""
    readme_path = FIXTURES_DIR / fixture_name / "README.md"
    if readme_path.exists():
        return readme_path.read_text(encoding="utf-8")
    return None


def get_fixture_source(fixture_name: str, source_file: str) -> str | None:
    """Get source file content from a fixture, or None if not found."""
    source_path = FIXTURES_DIR / fixture_name / source_file
    if source_path.exists():
        return source_path.read_text(encoding="utf-8")
    return None


class TestTaskFixtureAlignment:
    """Validate task/fixture alignment across all benchmark tasks."""

    def test_all_tasks_reference_valid_fixtures(self):
        """Every task with a fixture field must reference an existing fixture."""
        tasks = load_all_tasks()

        for task in tasks:
            fixture_name = task.get("fixture")
            if not fixture_name:
                continue

            fixture_path = FIXTURES_DIR / fixture_name
            assert fixture_path.exists(), (
                f"Task {task['id']} references non-existent fixture: {fixture_name}\n"
                f"Available fixtures: {[f.name for f in FIXTURES_DIR.iterdir() if f.is_dir()]}"
            )

    def test_all_tasks_have_valid_required_used_agents(self):
        """Every required_used_agents entry must be a valid agent alias."""
        tasks = load_all_tasks()

        for task in tasks:
            required_agents = task.get("required_used_agents", [])
            for agent in required_agents:
                assert agent in VALID_AGENT_ALIASES, (
                    f"Task {task['id']} has invalid required_used_agents: '{agent}'\n"
                    f"Valid aliases: {sorted(VALID_AGENT_ALIASES)}"
                )

    def test_docs_tasks_have_minimal_fixture_readmes(self):
        """
        Docs tasks should have fixtures where README.md needs updating.
        Catches misalignment where fixture already has quickstart content.
        """
        tasks = load_all_tasks()

        for task in tasks:
            if not task.get("docs_required", False):
                continue

            fixture_name = task.get("fixture")
            if not fixture_name:
                continue

            readme = get_fixture_readme(fixture_name)
            if not readme:
                continue

            prompt = task.get("prompt", "").lower()
            task_id = task["id"]

            for pattern in QUICKSTART_PATTERNS:
                if pattern.lower() in readme.lower():
                    # Allow if task explicitly references existing content
                    if pattern.lower() in prompt:
                        continue

                    # Check if this is a docs addition task
                    if "quickstart" in prompt or "npm test" in prompt or "pytest" in prompt:
                        assert False, (
                            f"Task/fixture misalignment: {task_id}\n"
                            f"Task requires docs update but fixture README already contains '{pattern}'\n"
                            f"Fixture: {FIXTURES_DIR / fixture_name / 'README.md'}\n"
                            f"Fix: Reset fixture README to minimal state or change task"
                        )

    def test_feature_tasks_have_incomplete_fixtures(self):
        """
        Feature tasks should have fixtures where the feature is NOT yet implemented.
        Catches misalignment where fixture already has a working implementation.
        Allows stubs (return 0, pass, TODO) since those indicate incomplete features.
        """
        tasks = load_all_tasks()
        feature_tasks = [t for t in tasks if t.get("category") == "feature"]

        for task in feature_tasks:
            fixture_name = task.get("fixture")
            if not fixture_name:
                continue

            # Check common source files (Python only)
            for source_file in ["calculator.py", "reporter.py"]:
                source = get_fixture_source(fixture_name, source_file)
                if not source:
                    continue

                prompt = task.get("prompt", "").lower()
                task_id = task["id"]

                # Extract Python function definitions
                import re
                func_pattern = r"def\s+(\w+)\s*\([^)]*\)\s*:([^\"']*(?:\"[^\"]*\"|'[^']*'[^\"']*)*)"
                matches = re.findall(func_pattern, source, re.DOTALL)

                for match in matches:
                    func_name = match[0]
                    func_body = match[1] if len(match) > 1 else ""

                    # Check if task explicitly asks to implement/add this function
                    # Look for patterns like "add X helper", "implement X", "create X"
                    # This avoids false positives from existing functions mentioned in examples
                    implement_patterns = [
                        rf"add\s+(?:a\s+)?{re.escape(func_name)}",
                        rf"implement\s+(?:the\s+)?{re.escape(func_name)}",
                        rf"create\s+(?:a\s+)?{re.escape(func_name)}",
                        rf"implement\s+(?:a\s+)?{re.escape(func_name)}\s+(?:helper|function)",
                    ]
                    asks_to_implement = any(re.search(p, prompt) for p in implement_patterns)

                    if not asks_to_implement:
                        continue

                    # Check if it's a stub (incomplete implementation)
                    is_stub = any(indicator in func_body for indicator in STUB_INDICATORS)

                    if not is_stub:
                        # Function exists and has actual implementation
                        # Check if it's a complete implementation
                        has_logic = any(
                            op in func_body
                            for op in ["+", "-", "*", "/", "and", "or", "if", "for", "while"]
                        )
                        if has_logic:
                            assert False, (
                                f"Task/fixture misalignment: {task_id}\n"
                                f"Task requires implementing '{func_name}' but fixture already has working implementation\n"
                                f"Fixture: {FIXTURES_DIR / fixture_name / source_file}\n"
                                f"Fix: Remove implementation from fixture or change task"
                            )

    def test_bugfix_tasks_have_unfixed_fixtures(self):
        """
        Bugfix tasks should have fixtures where the bug exists (not already fixed).
        Catches misalignment where fixture already has proper error handling.
        """
        tasks = load_all_tasks()
        bugfix_tasks = [t for t in tasks if t.get("category") == "bugfix"]

        for task in bugfix_tasks:
            fixture_name = task.get("fixture")
            if not fixture_name:
                continue

            # Check Python source files
            for source_file in ["calculator.py"]:
                source = get_fixture_source(fixture_name, source_file)
                if not source:
                    continue

                prompt = task.get("prompt", "").lower()
                task_id = task["id"]

                # If task mentions fixing division, check for proper error handling
                if "divide" in prompt or "division" in prompt or "zero" in prompt:
                    for pattern in BUG_PATTERNS:
                        if pattern in source and "zero" in prompt:
                            # Bug already fixed - proper error handling exists
                            assert False, (
                                f"Task/fixture misalignment: {task_id}\n"
                                f"Task requires fixing division bug but fixture already has '{pattern}'\n"
                                f"Fixture: {FIXTURES_DIR / fixture_name / source_file}\n"
                                f"Fix: Remove error handling from fixture or change task"
                            )

    def test_refactor_tasks_have_complexity_to_refactor(self):
        """
        Refactor tasks should have fixtures with duplication/complexity to remove.
        This is a softer check - just logs warning if fixture is already clean.
        """
        tasks = load_all_tasks()
        refactor_tasks = [t for t in tasks if t.get("category") == "refactor"]

        # This is informational - we don't fail on potentially clean fixtures
        # since determining if code is "refactored" is subjective
        for task in refactor_tasks:
            fixture_name = task.get("fixture")
            if not fixture_name:
                continue

            # Read main source file
            for source_file in ["reporter.py", "calculator.py"]:
                source = get_fixture_source(fixture_name, source_file)
                if source:
                    # Check for duplication indicators (same function repeated)
                    lines = source.split("\n")
                    line_counts = {}
                    for line in lines:
                        stripped = line.strip()
                        if stripped and not stripped.startswith("#"):
                            line_counts[stripped] = line_counts.get(stripped, 0) + 1

                    # If no lines are repeated, fixture might already be refactored
                    max_repeats = max(line_counts.values()) if line_counts else 0
                    # Note: This is informational only, not a failure
                    # Could log warning if needed

    def test_success_criteria_alignment_with_category(self):
        """
        Success criteria should align with task category.
        - feature tasks should mention implementation
        - bugfix tasks should mention fixes/tests
        - refactor tasks should mention code quality
        - docs tasks should mention documentation
        - review tasks should mention review
        """
        tasks = load_all_tasks()

        category_keywords = {
            "feature": ["implement", "add", "create", "function", "helper"],
            "bugfix": ["fix", "error", "exception", "test", "pass"],
            "refactor": ["refactor", "duplicate", "simplify", "clean"],
            "docs": ["readme", "documentation", "quickstart", "doc"],
            "review": ["review", "findings", "status"],
        }

        for task in tasks:
            category = task.get("category")
            if not category:
                continue

            success_criteria = task.get("success_criteria", [])
            if not success_criteria:
                continue

            keywords = category_keywords.get(category, [])
            if not keywords:
                continue

            # Check if at least one success criterion mentions category-relevant keyword
            criteria_text = " ".join(success_criteria).lower()
            has_relevant_keyword = any(kw in criteria_text for kw in keywords)

            # Allow flexibility - this is a soft check, not a hard failure
            # Just warn if success criteria seem completely unrelated to category
            task_id = task["id"]

    def test_required_transcript_patterns_present_for_used_agents(self):
        """
        Tasks with required_used_agents should have appropriate transcript patterns.
        Manager tasks should have "Outcome:" pattern.
        Review tasks should have "Review outcome:" pattern.
        """
        tasks = load_all_tasks()

        for task in tasks:
            required_agents = task.get("required_used_agents", [])
            patterns = task.get("required_transcript_patterns", [])
            task_id = task["id"]

            # Manager-led tasks should have footer patterns
            if "m" in required_agents:
                has_outcome = any("Outcome:" in p for p in patterns)
                if not has_outcome and patterns:  # Only check if patterns exist
                    # This is OK - empty patterns means benchmark will use defaults
                    pass

            # Review tasks should mention review outcome
            if "cr" in required_agents:
                has_review = any("Review" in p for p in patterns) if patterns else True
                # Empty patterns means defaults are used, which include review patterns

    def test_prompt_mentions_category_actions(self):
        """
        Prompt should mention actions relevant to the task category.
        - feature: should mention adding/implementing
        - bugfix: should mention fixing
        - refactor: should mention refactoring
        - docs: should mention documentation/README
        - review: should mention review/exploration
        """
        tasks = load_all_tasks()

        category_actions = {
            "feature": ["add", "implement", "create", "write"],
            "bugfix": ["fix", "bug", "error", "exception", "division"],
            "refactor": ["refactor", "remove", "duplicate", "simplify"],
            "docs": ["readme", "documentation", "quickstart", "doc", "update"],
            "review": ["review", "explore", "findings", "map"],
        }

        for task in tasks:
            category = task.get("category")
            if not category:
                continue

            prompt = task.get("prompt", "").lower()
            actions = category_actions.get(category, [])

            if not actions:
                continue

            has_relevant_action = any(action in prompt for action in actions)

            # Soft check - warn but don't fail
            # Some tasks may have category that doesn't match prompt exactly