"""Validate YAML frontmatter contract for bundled slash skills."""

from __future__ import annotations

from pathlib import Path


REQUIRED_FIELDS = {
    "name",
    "description",
    "agent",
    "context",
    "disable-model-invocation",
    "allowed-tools",
    "paths",
}


def _extract_frontmatter(md_path: Path) -> list[str]:
    lines = md_path.read_text(encoding="utf-8").splitlines()
    assert lines, f"{md_path.name}: file is empty"
    assert lines[0].strip() == "---", f"{md_path.name}: missing frontmatter start delimiter"

    try:
        end_index = lines[1:].index("---") + 1
    except ValueError as exc:
        raise AssertionError(f"{md_path.name}: missing frontmatter end delimiter") from exc

    if end_index + 1 < len(lines):
        assert lines[end_index + 1].strip() != "---", (
            f"{md_path.name}: duplicate frontmatter block detected"
        )

    return lines[1:end_index]


def _extract_scalar(frontmatter_lines: list[str], field: str) -> str:
    prefix = f"{field}:"
    for line in frontmatter_lines:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing frontmatter field '{field}'")


def _extract_list(frontmatter_lines: list[str], field: str) -> list[str]:
    items: list[str] = []
    capture = False
    for line in frontmatter_lines:
        stripped = line.strip()
        if stripped.startswith(f"{field}:"):
            inline_value = stripped.split(":", 1)[1].strip()
            if inline_value:
                items.append(inline_value)
            capture = True
            continue
        if capture and stripped.startswith("- "):
            items.append(stripped[2:].strip())
            continue
        if capture and stripped and not stripped.startswith("#"):
            break
    return items


def test_all_skills_have_required_frontmatter_fields() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = repo_root / "claudecfg" / "skills"
    skill_files = sorted(skill_dir.glob("*.md"))
    assert skill_files, "No skills found under claudecfg/skills"

    for skill_file in skill_files:
        frontmatter_lines = _extract_frontmatter(skill_file)
        frontmatter_text = "\n".join(frontmatter_lines)
        for field in REQUIRED_FIELDS:
            assert f"{field}:" in frontmatter_text, (
                f"{skill_file.name}: missing required frontmatter field '{field}'"
            )
        assert "disable-model-invocation: true" in frontmatter_text
        assert "context: fork" in frontmatter_text


def test_allowed_tools_and_paths_are_not_empty() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = repo_root / "claudecfg" / "skills"

    for skill_file in sorted(skill_dir.glob("*.md")):
        frontmatter_lines = _extract_frontmatter(skill_file)
        tools = _extract_list(frontmatter_lines, "allowed-tools")
        paths = _extract_list(frontmatter_lines, "paths")

        assert tools, f"{skill_file.name}: allowed-tools must declare at least one tool"
        assert paths, f"{skill_file.name}: paths must declare at least one path"


def test_skill_agents_match_known_agent_names() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    skill_dir = repo_root / "claudecfg" / "skills"
    agent_dir = repo_root / "claudecfg" / "agents"

    known_agents = set()
    for agent_file in sorted(agent_dir.glob("*.md")):
        frontmatter_lines = _extract_frontmatter(agent_file)
        known_agents.add(_extract_scalar(frontmatter_lines, "name"))
        known_agents.add(_extract_scalar(frontmatter_lines, "alias"))

    for skill_file in sorted(skill_dir.glob("*.md")):
        frontmatter_lines = _extract_frontmatter(skill_file)
        assert _extract_scalar(frontmatter_lines, "agent") in known_agents, (
            f"{skill_file.name}: agent must match a known agent name or alias"
        )
