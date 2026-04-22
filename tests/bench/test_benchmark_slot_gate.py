import importlib.util
from pathlib import Path


def load_slot_gate_module():
    repo_root = Path(__file__).resolve().parents[2]
    script_path = repo_root / "scripts" / "wait-for-benchmark-slot.py"
    spec = importlib.util.spec_from_file_location("wait_for_benchmark_slot", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_run_has_slot_when_among_two_oldest_active_runs():
    module = load_slot_gate_module()
    runs = [
        {"id": 300, "created_at": "2026-04-03T20:00:03Z"},
        {"id": 100, "created_at": "2026-04-03T20:00:01Z"},
        {"id": 200, "created_at": "2026-04-03T20:00:02Z"},
    ]

    has_slot, allowed_ids = module.current_run_has_slot(current_run_id=200, runs=runs, max_active=2)

    assert has_slot is True
    assert allowed_ids == [100, 200]


def test_current_run_waits_when_third_oldest_active_run():
    module = load_slot_gate_module()
    runs = [
        {"id": 100, "created_at": "2026-04-03T20:00:01Z"},
        {"id": 200, "created_at": "2026-04-03T20:00:02Z"},
        {"id": 300, "created_at": "2026-04-03T20:00:03Z"},
    ]

    has_slot, allowed_ids = module.current_run_has_slot(current_run_id=300, runs=runs, max_active=2)

    assert has_slot is False
    assert allowed_ids == [100, 200]
