"""Tests for hook scenario and case manifests."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOKS_DIR = REPO_ROOT / "tests" / "hooks"
FIXTURES_DIR = HOOKS_DIR / "fixtures"
PROJECTS_DIR = HOOKS_DIR / "projects"
HOOK_SCRIPTS_DIR = REPO_ROOT / "claudecfg" / "hooks"


def load_manifest(name: str) -> list[dict]:
    manifest_path = HOOKS_DIR / name
    with manifest_path.open("r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    assert isinstance(manifest, list), f"{name} must be a JSON array"
    return manifest


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return REPO_ROOT / raw_path


def assert_path_exists(raw_path: str, label: str) -> None:
    path = resolve_path(raw_path)
    assert path.exists(), f"{label} missing: {path}"


def validate_case_entry(case: dict) -> None:
    assert isinstance(case, dict)
    assert isinstance(case.get("name"), str) and case["name"], "case name must be non-empty"
    assert isinstance(case.get("script"), str) and case["script"], f"{case['name']}: script must be non-empty"
    assert isinstance(case.get("stdin"), str) and case["stdin"], f"{case['name']}: stdin must be non-empty"

    assert_path_exists(case["script"], f"{case['name']} script")
    assert_path_exists(case["stdin"], f"{case['name']} stdin")

    if "seed_state" in case and case["seed_state"]:
        assert_path_exists(case["seed_state"], f"{case['name']} seed_state")

    cwd = case.get("cwd")
    if cwd:
        assert_path_exists(cwd, f"{case['name']} cwd")

    env = case.get("env")
    assert env is None or isinstance(env, dict), f"{case['name']}: env must be an object when present"


def validate_scenario_entry(scenario: dict) -> None:
    assert isinstance(scenario, dict)
    assert isinstance(scenario.get("name"), str) and scenario["name"], "scenario name must be non-empty"
    assert isinstance(scenario.get("session_id"), str) and scenario["session_id"], (
        f"{scenario['name']}: session_id must be non-empty"
    )
    assert isinstance(scenario.get("steps"), list) and scenario["steps"], (
        f"{scenario['name']}: steps must be a non-empty array"
    )

    if "seed_state" in scenario and scenario["seed_state"]:
        assert_path_exists(scenario["seed_state"], f"{scenario['name']} seed_state")

    names: set[str] = set()
    for step in scenario["steps"]:
        assert isinstance(step, dict), f"{scenario['name']}: each step must be an object"
        assert isinstance(step.get("name"), str) and step["name"], f"{scenario['name']}: step name must be non-empty"
        assert step["name"] not in names, f"{scenario['name']}: duplicate step name {step['name']}"
        names.add(step["name"])

        assert isinstance(step.get("script"), str) and step["script"], (
            f"{scenario['name']}::{step['name']}: script must be non-empty"
        )
        assert isinstance(step.get("stdin"), str) and step["stdin"], (
            f"{scenario['name']}::{step['name']}: stdin must be non-empty"
        )
        assert_path_exists(step["script"], f"{scenario['name']}::{step['name']} script")
        assert_path_exists(step["stdin"], f"{scenario['name']}::{step['name']} stdin")

        if "seed_state" in step and step["seed_state"]:
            assert_path_exists(step["seed_state"], f"{scenario['name']}::{step['name']} seed_state")

        cwd = step.get("cwd")
        if cwd:
            assert_path_exists(cwd, f"{scenario['name']}::{step['name']} cwd")

        env = step.get("env")
        assert env is None or isinstance(env, dict), f"{scenario['name']}::{step['name']}: env must be an object when present"


def test_hook_cases_manifest_is_valid():
    cases = load_manifest("cases.json")
    assert len(cases) >= 1

    names: set[str] = set()
    for case in cases:
        validate_case_entry(case)
        assert case["name"] not in names, f"duplicate case name: {case['name']}"
        names.add(case["name"])


def test_hook_scenarios_manifest_is_valid():
    scenarios = load_manifest("scenarios.json")
    assert len(scenarios) >= 1

    names: set[str] = set()
    for scenario in scenarios:
        validate_scenario_entry(scenario)
        assert scenario["name"] not in names, f"duplicate scenario name: {scenario['name']}"
        names.add(scenario["name"])
