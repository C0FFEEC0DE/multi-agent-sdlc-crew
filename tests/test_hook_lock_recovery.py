"""Regression tests for the state-lock stale-recovery in claudecfg/hooks/lib.sh.

The hook state file is guarded by a portable mkdir-based advisory lock
(lockdir next to the state file). When a hook process is killed mid-update
the RETURN trap that releases the lock never fires, orphaning the lockdir.
These tests plant stale lockdirs and assert the hook recovers quickly
instead of spinning for ~10s (dead holder) or forever (PID reuse).

They subprocess-execute the real stop-guard.sh with HOME pointed at a
tmp dir so STATE_ROOT (~/.claude/state) is isolated.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
STOP_GUARD = REPO_ROOT / "claudecfg" / "hooks" / "stop-guard.sh"

# Recovery must be far faster than the OLD 10-12s spin. Leave headroom for
# process startup + jq, but catch any regression to the busy-wait.
RECOVERY_BUDGET_SECONDS = 5.0


def _safe_session_id(session_id: str) -> str:
    # Mirrors safe_session_id() in lib.sh: tr -c 'A-Za-z0-9._-' '_'
    return re.sub(r"[^A-Za-z0-9._-]", "_", session_id)


def _state_dir(home: Path) -> Path:
    return home / ".claude" / "state"


def _state_file(home: Path, session_id: str) -> Path:
    return _state_dir(home) / f"{_safe_session_id(session_id)}.json"


def _lock_dir(home: Path, session_id: str) -> Path:
    sf = _state_file(home, session_id)
    return sf.parent / f"{sf.name}.lock"


def _seed_state(home: Path, session_id: str) -> Path:
    sf = _state_file(home, session_id)
    sf.parent.mkdir(parents=True, exist_ok=True)
    # An existing state file makes stop-guard reach clear_loop_block, which
    # unconditionally writes -> acquires the lock -> exercises recovery.
    sf.write_text("{}", encoding="utf-8")
    return sf


def _plant_lock(home: Path, session_id: str, *, age_seconds: int | None,
                pid: str = "999999") -> None:
    lk = _lock_dir(home, session_id)
    lk.mkdir(parents=True, exist_ok=True)
    (lk / "pid").write_text(pid, encoding="utf-8")
    if age_seconds is not None:
        (lk / "created_epoch").write_text(
            str(int(time.time()) - age_seconds), encoding="utf-8"
        )
    # age_seconds=None leaves created_epoch absent (missing-epoch orphan).


def _run_stop_guard(home: Path, session_id: str,
                    timeout: float = 15.0) -> subprocess.CompletedProcess:
    env = {
        "HOME": str(home),
        "PATH": os.environ.get("PATH", ""),
    }
    payload = {
        "session_id": session_id,
        "transcript_path": "",
        "cwd": str(REPO_ROOT),
    }
    return subprocess.run(
        [str(STOP_GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _assert_recovered(home: Path, session_id: str, elapsed: float,
                      result: subprocess.CompletedProcess) -> None:
    assert result.returncode == 0, (
        f"stop-guard exited {result.returncode}\nstderr:\n{result.stderr}"
    )
    assert elapsed < RECOVERY_BUDGET_SECONDS, (
        f"stale lock not recovered within budget: {elapsed:.2f}s "
        f"(regression to the busy-wait spin)\nstderr:\n{result.stderr}"
    )
    # Recovery acquired + released the lock (RETURN trap rmdir'd it). A
    # give-up via the backstop would leave the lockdir in place.
    assert not _lock_dir(home, session_id).exists(), (
        "stale lockdir still present after run — recovery did not acquire"
    )
    # And the state write actually landed (clear_loop_block resets the
    # stop block counters to 0), proving the critical section completed.
    sf = _state_file(home, session_id)
    state = json.loads(sf.read_text(encoding="utf-8"))
    assert state.get("stop_block_count") == 0, (
        f"state write did not complete: stop_block_count={state.get('stop_block_count')!r}"
    )


def test_stale_lock_dead_holder_recovered_fast(tmp_path: Path) -> None:
    """A stale lock whose holder PID is dead must break on the first check,
    not after a ~10s spin (the original bug)."""
    home = tmp_path
    sid = "locktest-dead-pid"
    _seed_state(home, sid)
    _plant_lock(home, sid, age_seconds=3600, pid="999999")

    t0 = time.monotonic()
    result = _run_stop_guard(home, sid)
    elapsed = time.monotonic() - t0

    _assert_recovered(home, sid, elapsed, result)


def test_stale_lock_pid_reuse_recovered_fast(tmp_path: Path) -> None:
    """A stale lock whose recorded PID was reused by a live, owned process
    must still break on age alone. The old code checked `kill -0` and hung
    forever here; this guards that regression."""
    home = tmp_path
    sid = "locktest-pid-reuse"
    _seed_state(home, sid)
    # A genuinely alive process owned by the test runner, simulating PID reuse.
    sleeper = subprocess.Popen(
        ["sleep", "300"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert sleeper.poll() is None, "sleeper process did not start"
        _plant_lock(home, sid, age_seconds=3600, pid=str(sleeper.pid))

        t0 = time.monotonic()
        result = _run_stop_guard(home, sid, timeout=15.0)
        elapsed = time.monotonic() - t0

        _assert_recovered(home, sid, elapsed, result)
    finally:
        sleeper.terminate()
        sleeper.wait(timeout=5)


def test_missing_epoch_orphan_recovered_bounded(tmp_path: Path) -> None:
    """An orphaned lockdir with no created_epoch (holder killed in the
    microsecond window before recording its age) must be recovered by the
    missing-epoch streak in bounded time, not spin forever."""
    home = tmp_path
    sid = "locktest-no-epoch"
    _seed_state(home, sid)
    _plant_lock(home, sid, age_seconds=None)  # no created_epoch file

    t0 = time.monotonic()
    result = _run_stop_guard(home, sid, timeout=15.0)
    elapsed = time.monotonic() - t0

    _assert_recovered(home, sid, elapsed, result)