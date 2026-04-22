import importlib.util
import json
from pathlib import Path


def load_matrix_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "build-benchmark-matrix.py"
    spec = importlib.util.spec_from_file_location("build_benchmark_matrix", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_chunk_task_paths_even_distribution():
    module = load_matrix_module()
    result = module.chunk_task_paths(["a", "b", "c", "d", "e"], 2)
    assert result == [["a", "c", "e"], ["b", "d"]]


def test_chunk_task_paths_fewer_tasks_than_shards():
    module = load_matrix_module()
    result = module.chunk_task_paths(["a"], 3)
    assert result == [["a"]]


def test_chunk_task_paths_empty():
    module = load_matrix_module()
    assert module.chunk_task_paths([], 2) == []


def test_chunk_task_paths_single_shard():
    module = load_matrix_module()
    result = module.chunk_task_paths(["a", "b", "c"], 1)
    assert result == [["a", "b", "c"]]


def test_chunk_task_paths_more_shards_than_tasks():
    module = load_matrix_module()
    result = module.chunk_task_paths(["a", "b"], 5)
    assert result == [["a"], ["b"]]


def test_build_matrix_shard_metadata():
    module = load_matrix_module()
    result = module.build_matrix(["a", "b", "c", "d", "e"], 3)
    assert len(result) == 3
    assert result[0]["shard_index"] == 1
    assert result[0]["task_count"] == 2
    assert result[0]["task_files"] == "a\nd"
    assert result[1]["shard_index"] == 2
    assert result[1]["task_count"] == 2
    assert result[1]["task_files"] == "b\ne"
    assert result[2]["shard_index"] == 3
    assert result[2]["task_count"] == 1
    assert result[2]["task_files"] == "c"


def test_build_matrix_empty():
    module = load_matrix_module()
    assert module.build_matrix([], 2) == []
