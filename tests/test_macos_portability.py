"""Tests for macOS portability in shell scripts.

These tests follow TDD: they FAIL before the fix and PASS after.
They verify that no GNU/Linux-only constructs remain in scripts that
need to run on macOS (BSD userland + bash 3.2).
"""

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
TESTS_INSTALL_DIR = REPO_ROOT / "tests" / "install"
HOOKS_DIR = REPO_ROOT / "claudecfg" / "hooks"

# Shell scripts that are executed directly and must be portable.
PORTABLE_SHELL_SCRIPTS = list(SCRIPTS_DIR.glob("*.sh")) + list(TESTS_INSTALL_DIR.glob("*.sh"))

# All hook scripts must also be portable.
HOOK_SCRIPTS = list(HOOKS_DIR.glob("*.sh"))

# GNU/Linux-only constructs that must NOT appear in portable scripts.
# These were all fixed in commits f160252 and bbe0144 but regressions
# are possible.
GNU_ONLY_PATTERNS = {
    # Associative arrays — bash 3.2 (macOS /bin/bash) does not support declare -A.
    "declare -A": re.compile(r"\bdeclare\s+-A\b"),
    # PCRE grep — BSD grep does not support -P.
    "grep -P": re.compile(r"\bgrep\s+-P\b"),
    # flock is Linux-only; macOS has no equivalent.
    "flock": re.compile(r"\bflock\b"),
    # mapfile / readarray — bash 3.2 does not support them.
    "mapfile": re.compile(r"\bmapfile\b"),
    "readarray": re.compile(r"\breadarray\b"),
    # ${var,,} case-folding — bash 3.2 does not support it.
    "${var,,}": re.compile(r"\$\{[^}]*,,[^}]*\}"),
    # find -printf is a GNU extension; BSD find does not have it.
    "find -printf": re.compile(r"\bfind\b[^;]*-printf\b"),
}

# Constructs that are allowed ONLY inside runtime-probe guards
# (e.g. `if stat -c%s … >/dev/null 2>&1; then … else stat -f%z … fi`).
PROBE_OK_PATTERNS = {
    # stat -c%s is allowed as the probe branch of a GNU/BSD runtime check.
    "stat -c%s": re.compile(r"\bstat\s+-c%s\b"),
}


def _extract_non_comment_lines(content: str) -> list[str]:
    """Return lines that are not pure shell comments (but keep inline comments)."""
    result = []
    for line in content.splitlines():
        stripped = line.strip()
        # Skip pure comment lines and shebang
        if stripped.startswith("#") or stripped.startswith("#!/"):
            continue
        result.append(line)
    return result


class TestValidateShMacOSPortability:
    """Bug: scripts/validate.sh still uses GNU find -printf."""

    def test_no_find_printf(self):
        """find -printf is GNU-only and breaks on macOS/BSD."""
        content = (SCRIPTS_DIR / "validate.sh").read_text()
        matches = list(GNU_ONLY_PATTERNS["find -printf"].finditer(content))
        assert not matches, (
            f"scripts/validate.sh contains {len(matches)} GNU find -printf usage(s). "
            f"Replace with portable 'find … | sed \"s|.*/|||\"'."
        )

    def test_no_grep_p_outside_comments(self):
        """grep -P (PCRE) is not supported by BSD grep."""
        content = (SCRIPTS_DIR / "validate.sh").read_text()
        non_comment_lines = _extract_non_comment_lines(content)
        code = "\n".join(non_comment_lines)
        matches = list(GNU_ONLY_PATTERNS["grep -P"].finditer(code))
        assert not matches, (
            f"scripts/validate.sh contains {len(matches)} 'grep -P' usage(s) outside comments. "
            f"Replace with 'sed -E' for portable extended regex."
        )

    def test_no_declare_a_outside_comments(self):
        """bash 3.2 (macOS /bin/bash) does not support declare -A."""
        content = (SCRIPTS_DIR / "validate.sh").read_text()
        non_comment_lines = _extract_non_comment_lines(content)
        code = "\n".join(non_comment_lines)
        matches = list(GNU_ONLY_PATTERNS["declare -A"].finditer(code))
        assert not matches, (
            f"scripts/validate.sh contains {len(matches)} 'declare -A' usage(s) outside comments. "
            f"Use parallel indexed arrays with a lookup function instead."
        )


class TestInstallSmokeShMacOSPortability:
    """Bug: tests/install/install-smoke.sh uses sha256sum without macOS fallback."""

    def test_uses_portable_checksum_command(self):
        """sha256sum is not installed by default on macOS; shasum -a 256 is."""
        content = (TESTS_INSTALL_DIR / "install-smoke.sh").read_text()

        # The script must define a SHA256_CMD (or similar) that probes for
        # sha256sum and falls back to shasum -a 256.
        has_probe = "sha256sum" in content and "shasum" in content
        assert has_probe, (
            "tests/install/install-smoke.sh must probe for sha256sum vs shasum -a 256 "
            "to work on stock macOS. Add a command probe and use a variable."
        )

    def test_no_bare_sha256sum_calls(self):
        """Bare 'sha256sum' (not via a variable or probe) breaks on macOS."""
        content = (TESTS_INSTALL_DIR / "install-smoke.sh").read_text()
        lines = content.splitlines()
        bare_lines = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Skip comments and shebang
            if stripped.startswith("#") or stripped.startswith("#!/"):
                continue
            if "sha256sum" in line and "command -v sha256sum" not in line:
                # Allow variable definitions (SHA256_CMD=(sha256sum))
                # and variable references (${SHA256_CMD[@]} or $SHA256_CMD)
                if re.search(r"\bsha256sum\b", line) and not re.search(r"\$\{?SHA256", line) \
                        and not re.search(r"\bSHA256_CMD\s*=.*sha256sum", line):
                    bare_lines.append((i, line.strip()))

        assert not bare_lines, (
            f"tests/install/install-smoke.sh has {len(bare_lines)} bare 'sha256sum' call(s). "
            f"Each must go through a probed variable. Offending lines:\n"
            + "\n".join(f"  line {n}: {line_text}" for n, line_text in bare_lines)
        )


class TestHooksMacOSPortabilityRegression:
    """Regression: previously-fixed GNU constructs must not reappear in hooks."""

    def test_no_flock_in_hooks(self):
        """flock is Linux-only; macOS has no equivalent."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            non_comment_lines = _extract_non_comment_lines(content)
            code = "\n".join(non_comment_lines)
            matches = list(GNU_ONLY_PATTERNS["flock"].finditer(code))
            assert not matches, (
                f"{script.name} contains {len(matches)} 'flock' usage(s) outside comments. "
                f"Use mkdir atomic locking instead."
            )

    def test_no_mapfile_in_hooks(self):
        """mapfile is bash 4+; macOS /bin/bash is 3.2."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            matches = list(GNU_ONLY_PATTERNS["mapfile"].finditer(content))
            assert not matches, (
                f"{script.name} contains {len(matches)} 'mapfile' usage(s). "
                f"Use 'while IFS= read -r' loop instead."
            )

    def test_no_readarray_in_hooks(self):
        """readarray is bash 4+; macOS /bin/bash is 3.2."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            matches = list(GNU_ONLY_PATTERNS["readarray"].finditer(content))
            assert not matches, (
                f"{script.name} contains {len(matches)} 'readarray' usage(s). "
                f"Use 'while IFS= read -r' loop instead."
            )

    def test_no_declare_a_in_hooks(self):
        """declare -A is bash 4+; macOS /bin/bash is 3.2."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            matches = list(GNU_ONLY_PATTERNS["declare -A"].finditer(content))
            assert not matches, (
                f"{script.name} contains {len(matches)} 'declare -A' usage(s). "
                f"Use parallel indexed arrays instead."
            )

    def test_no_grep_p_in_hooks(self):
        """grep -P (PCRE) is not supported by BSD grep."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            non_comment_lines = _extract_non_comment_lines(content)
            code = "\n".join(non_comment_lines)
            matches = list(GNU_ONLY_PATTERNS["grep -P"].finditer(code))
            assert not matches, (
                f"{script.name} contains {len(matches)} 'grep -P' usage(s) outside comments. "
                f"Use 'sed -E' for portable extended regex."
            )

    def test_no_var_case_folding_in_hooks(self):
        """${var,,} is bash 4+; macOS /bin/bash is 3.2."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            non_comment_lines = _extract_non_comment_lines(content)
            code = "\n".join(non_comment_lines)
            matches = list(GNU_ONLY_PATTERNS["${var,,}"].finditer(code))
            assert not matches, (
                f"{script.name} contains {len(matches)} '${{var,,}}' usage(s) outside comments. "
                f"Use 'tr \"[:upper:]\" \"[:lower:]\"' instead."
            )

    def test_stat_probe_is_guarded(self):
        """stat -c%s is only allowed inside a runtime GNU/BSD probe."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            lines = content.splitlines()
            for i, line in enumerate(lines, 1):
                if PROBE_OK_PATTERNS["stat -c%s"].search(line):
                    # Verify this line is inside a probe guard (stat -c%s inside
                    # an if/else where stat -f%z also appears).
                    context = "\n".join(lines[max(0, i - 5):i + 5])
                    has_bsd_branch = "stat -f%z" in context
                    assert has_bsd_branch, (
                        f"{script.name} line {i} uses 'stat -c%s' without a BSD fallback. "
                        f"Wrap in: if stat -c%s … >/dev/null 2>&1; then … else stat -f%z … fi"
                    )

    def test_no_find_printf_in_hooks(self):
        """find -printf is GNU-only and breaks on macOS/BSD."""
        for script in HOOK_SCRIPTS:
            content = script.read_text()
            non_comment_lines = _extract_non_comment_lines(content)
            code = "\n".join(non_comment_lines)
            matches = list(GNU_ONLY_PATTERNS["find -printf"].finditer(code))
            assert not matches, (
                f"{script.name} contains {len(matches)} 'find -printf' usage(s) outside comments. "
                f"Use 'find … | sed \"s|.*/|||\"' instead."
            )
