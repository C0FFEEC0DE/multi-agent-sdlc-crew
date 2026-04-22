#!/usr/bin/env python3

import argparse
import json
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-list-file", required=True)
    parser.add_argument("--max-shards", type=int, default=3)
    return parser.parse_args()


def load_task_paths(task_list_file: pathlib.Path) -> list[str]:
    if not task_list_file.exists():
        return []
    return [line.strip() for line in task_list_file.read_text(encoding="utf-8").splitlines() if line.strip()]


def chunk_task_paths(task_paths: list[str], max_shards: int) -> list[list[str]]:
    if not task_paths:
        return []
    shard_count = max(1, min(max_shards, len(task_paths)))
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    for index, task_path in enumerate(task_paths):
        shards[index % shard_count].append(task_path)
    return [shard for shard in shards if shard]


def build_matrix(task_paths: list[str], max_shards: int) -> list[dict[str, object]]:
    include: list[dict[str, object]] = []
    for shard_index, shard_paths in enumerate(chunk_task_paths(task_paths, max_shards), start=1):
        include.append(
            {
                "shard_index": shard_index,
                "task_files": "\n".join(shard_paths),
                "task_count": len(shard_paths),
            }
        )
    return include


def main() -> None:
    args = parse_args()
    task_paths = load_task_paths(pathlib.Path(args.task_list_file))
    print(json.dumps(build_matrix(task_paths, args.max_shards), ensure_ascii=False))


if __name__ == "__main__":
    main()
