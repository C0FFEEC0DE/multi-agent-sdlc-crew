#!/usr/bin/env python3

import argparse
import email.utils
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Iterable


BEHAVIOR_WORKFLOW_NAMES = {
    "Behavior Benchmark Smoke",
    "Behavior Benchmark Full",
    "Behavior Benchmark Subagents Smoke",
}

ACTIVE_STATUSES = {"queued", "in_progress", "waiting", "pending", "requested"}


RATE_LIMIT_BODY_MARKERS = frozenset(["rate_limit_exceeded", "rate limit exceeded", "rate limit"])

def _read_body_once(exc: urllib.error.HTTPError) -> str:
    """Cache the response body on the exception so we can read it more than once."""
    cached = getattr(exc, "_body_cache", None)
    if cached is not None:
        return cached
    body = exc.read().decode("utf-8", errors="replace")
    exc._body_cache = body  # type: ignore[attr-defined]
    return body


def is_github_rate_limit(exc: urllib.error.HTTPError) -> bool:
    """Return True if this HTTP 403 is a GitHub API rate-limit response."""
    if exc.code != 403:
        return False
    remaining = exc.headers.get("X-RateLimit-Remaining", "")
    if remaining == "0":
        return True
    body = _read_body_once(exc)
    return any(marker in body.lower() for marker in RATE_LIMIT_BODY_MARKERS)


def parse_retry_after(value: str | None) -> int | None:
    """Parse a Retry-After header (seconds or HTTP-date). Return None on failure."""
    if not value:
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        seconds = int(candidate)
    except ValueError:
        seconds = None
    if seconds is not None:
        return max(0, seconds)
    try:
        when = email.utils.parsedate_to_datetime(candidate)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    delta = (when - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(delta))


def handle_rate_limit(exc: urllib.error.HTTPError) -> int | None:
    """Sleep for the Retry-After period on a rate-limit hit; return None to retry."""
    parsed = parse_retry_after(exc.headers.get("Retry-After"))
    wait_seconds = parsed if parsed is not None else 60
    print(
        f"GitHub API rate limit hit (HTTP 403). "
        f"Retrying after {wait_seconds}s (Retry-After header, default 60).",
        file=sys.stderr,
    )
    time.sleep(wait_seconds)
    return None  # signal caller to continue/retry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-run-id", type=int, required=True)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--max-active", type=int, default=2)
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--api-url", default=os.environ.get("GITHUB_API_URL", "https://api.github.com"))
    return parser.parse_args()


def build_request(url: str, token: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "claude-crew-benchmark-slot-gate",
        },
    )


def fetch_active_behavior_runs(*, api_url: str, repo: str, token: str, head_sha: str) -> list[dict]:
    url = f"{api_url}/repos/{repo}/actions/runs?per_page=100"
    request = build_request(url, token)
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    runs = payload.get("workflow_runs", [])
    selected: list[dict] = []
    for run in runs:
        if run.get("name") not in BEHAVIOR_WORKFLOW_NAMES:
            continue
        if run.get("head_sha") != head_sha:
            continue
        if run.get("status") not in ACTIVE_STATUSES:
            continue
        selected.append(run)
    return selected


def order_active_runs(runs: Iterable[dict]) -> list[dict]:
    return sorted(
        runs,
        key=lambda run: (
            run.get("created_at", ""),
            int(run.get("id", 0)),
        ),
    )


def current_run_has_slot(*, current_run_id: int, runs: Iterable[dict], max_active: int) -> tuple[bool, list[int]]:
    ordered = order_active_runs(runs)
    allowed_run_ids = [int(run["id"]) for run in ordered[:max_active]]
    return current_run_id in allowed_run_ids, allowed_run_ids


def handle_transient_error(exc: Exception, attempt: int) -> bool:
    """Log a transient error and optionally retry. Returns True if we should retry."""
    max_retries = 5
    if attempt >= max_retries:
        return False
    delay = min(2 ** attempt, 60)
    print(f"Transient error: {exc}. Retry {attempt + 1}/{max_retries} after {delay}s.", file=sys.stderr)
    time.sleep(delay)
    return True


def main() -> int:
    args = parse_args()
    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repo:
        print("GITHUB_REPOSITORY or --repo is required", file=sys.stderr)
        return 2
    if not token:
        print("GITHUB_TOKEN is required", file=sys.stderr)
        return 2

    deadline = time.monotonic() + args.timeout_seconds
    transient_attempt = 0
    while True:
        try:
            active_runs = fetch_active_behavior_runs(
                api_url=args.api_url,
                repo=args.repo,
                token=token,
                head_sha=args.head_sha,
            )
            transient_attempt = 0
        except urllib.error.HTTPError as exc:
            if is_github_rate_limit(exc):
                result = handle_rate_limit(exc)
                if result is not None:
                    return result
                continue  # retry after sleeping
            if exc.code in {500, 502, 503, 504}:
                if handle_transient_error(exc, transient_attempt):
                    transient_attempt += 1
                    continue
            try:
                body_snippet = _read_body_once(exc)[:500]
            except Exception:  # noqa: BLE001 - body may already be consumed
                body_snippet = ""
            if body_snippet:
                print(
                    f"GitHub API request failed with HTTP {exc.code}: {body_snippet}",
                    file=sys.stderr,
                )
            else:
                print(f"GitHub API request failed with HTTP {exc.code}", file=sys.stderr)
            return 1
        except urllib.error.URLError as exc:
            if handle_transient_error(exc, transient_attempt):
                transient_attempt += 1
                continue
            print(f"GitHub API request failed: {exc}", file=sys.stderr)
            return 1

        has_slot, allowed_ids = current_run_has_slot(
            current_run_id=args.current_run_id,
            runs=active_runs,
            max_active=args.max_active,
        )
        active_ids = [int(run["id"]) for run in order_active_runs(active_runs)]
        print(
            f"Active benchmark workflow runs for {args.head_sha[:12]}: {active_ids}. "
            f"Allowed now: {allowed_ids}."
        )
        if has_slot:
            print(f"Run {args.current_run_id} has a benchmark slot.")
            return 0
        if time.monotonic() >= deadline:
            print(
                f"Timed out waiting for benchmark slot after {args.timeout_seconds}s. "
                f"Current run {args.current_run_id} never entered the first {args.max_active}.",
                file=sys.stderr,
            )
            return 1
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
