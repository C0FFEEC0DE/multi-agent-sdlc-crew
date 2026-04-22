import importlib.util
from pathlib import Path


def load_slot_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "wait-for-benchmark-slot.py"
    spec = importlib.util.spec_from_file_location("wait_for_benchmark_slot", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_order_active_runs_sorted_by_created_at_then_id():
    module = load_slot_module()
    runs = [
        {"id": "200", "created_at": "2026-01-01T00:00:02Z"},
        {"id": "100", "created_at": "2026-01-01T00:00:01Z"},
        {"id": "300", "created_at": "2026-01-01T00:00:01Z"},
    ]
    ordered = module.order_active_runs(runs)
    assert [r["id"] for r in ordered] == ["100", "300", "200"]


def test_order_active_runs_missing_created_at():
    module = load_slot_module()
    # Empty string ("") sorts BEFORE any non-empty string in Python's lexicographic
    # sort, so a run with no created_at key comes first.
    runs = [
        {"id": "2"},
        {"id": "1", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "3", "created_at": "2026-01-01T00:00:00Z"},
    ]
    ordered = module.order_active_runs(runs)
    # "2" (empty created_at="") sorts first; "1"/"3" tie on created_at, broken by id
    assert [r["id"] for r in ordered] == ["2", "1", "3"]


def test_has_slot_current_run_in_first_n():
    module = load_slot_module()
    runs = [
        {"id": "1", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "2", "created_at": "2026-01-01T00:00:01Z"},
        {"id": "3", "created_at": "2026-01-01T00:00:02Z"},
    ]
    has_slot, allowed = module.current_run_has_slot(current_run_id=2, runs=runs, max_active=2)
    assert has_slot is True
    assert allowed == [1, 2]


def test_has_slot_current_run_not_in_first_n():
    module = load_slot_module()
    runs = [
        {"id": "1", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "2", "created_at": "2026-01-01T00:00:01Z"},
    ]
    has_slot, allowed = module.current_run_has_slot(current_run_id=3, runs=runs, max_active=2)
    assert has_slot is False
    assert allowed == [1, 2]


def test_has_slot_exactly_max_active():
    module = load_slot_module()
    runs = [
        {"id": "5", "created_at": "2026-01-01T00:00:00Z"},
        {"id": "10", "created_at": "2026-01-01T00:00:01Z"},
    ]
    has_slot, allowed = module.current_run_has_slot(current_run_id=10, runs=runs, max_active=2)
    assert has_slot is True
    assert allowed == [5, 10]


class FakeHeaders:
    def __init__(self, data):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)


class FakeHTTPError:
    def __init__(self, code, headers_data, body_bytes):
        self.code = code
        self.headers = FakeHeaders(headers_data)
        self._body = body_bytes

    def read(self):
        return self._body


def test_is_github_rate_limit_header_zero():
    module = load_slot_module()
    exc = FakeHTTPError(
        code=403,
        headers_data={"X-RateLimit-Remaining": "0"},
        body_bytes=b"{}",
    )
    assert module.is_github_rate_limit(exc) is True


def test_is_github_rate_limit_body_marker():
    module = load_slot_module()
    exc = FakeHTTPError(
        code=403,
        headers_data={},
        body_bytes=b'{"message": "rate_limit_exceeded"}',
    )
    assert module.is_github_rate_limit(exc) is True


def test_is_github_rate_limit_not_403():
    module = load_slot_module()
    exc = FakeHTTPError(
        code=429,
        headers_data={},
        body_bytes=b"{}",
    )
    assert module.is_github_rate_limit(exc) is False


def test_is_github_rate_limit_403_no_marker():
    module = load_slot_module()
    exc = FakeHTTPError(
        code=403,
        headers_data={},
        body_bytes=b'{"message": "forbidden"}',
    )
    assert module.is_github_rate_limit(exc) is False
