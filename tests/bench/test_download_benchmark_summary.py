import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pytest


def load_download_module():
    repo_root = Path(__file__).resolve().parents[2]
    module_path = repo_root / "scripts" / "download-benchmark-summary.py"
    spec = importlib.util.spec_from_file_location("download_benchmark_summary", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def build_zip(entries):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_find_artifact_returns_named_nonexpired_artifact():
    module = load_download_module()
    artifact = module.find_artifact(
        [
            {"id": 1, "name": "other", "expired": False},
            {"id": 2, "name": "behavior-benchmark-smoke-123", "expired": False},
        ],
        "behavior-benchmark-smoke-123",
    )

    assert artifact["id"] == 2


def test_find_artifact_rejects_expired_match():
    module = load_download_module()
    with pytest.raises(RuntimeError, match="Artifact not found or expired"):
        module.find_artifact(
            [{"id": 2, "name": "behavior-benchmark-smoke-123", "expired": True}],
            "behavior-benchmark-smoke-123",
        )


def test_extract_summary_bytes_reads_nested_summary_json():
    module = load_download_module()
    summary_bytes = module.extract_summary_bytes(
        build_zip(
            {
                "bench-output/summary.json": '{"status":"ok"}',
                "bench-output/benchmark-report.md": "# report",
            }
        )
    )

    assert json.loads(summary_bytes.decode("utf-8")) == {"status": "ok"}


def test_extract_summary_bytes_requires_summary_file():
    module = load_download_module()
    with pytest.raises(RuntimeError, match="summary.json"):
        module.extract_summary_bytes(build_zip({"report.md": "missing summary"}))


def test_download_summary_fetches_artifact_listing_then_redirected_zip(monkeypatch):
    module = load_download_module()
    calls = []

    def fake_get_json(url, token):
        calls.append(("json", url, token))
        return {
            "artifacts": [
                {"id": 42, "name": "behavior-benchmark-smoke-123", "expired": False},
            ]
        }

    def fake_get_redirect_url(url, token):
        calls.append(("redirect", url, token))
        return "https://example.invalid/artifact.zip"

    def fake_public_get_bytes(url):
        calls.append(("public-bytes", url))
        return build_zip({"summary.json": '{"ok": true}'})

    monkeypatch.setattr(module, "github_get_json", fake_get_json)
    monkeypatch.setattr(module, "github_get_redirect_url", fake_get_redirect_url)
    monkeypatch.setattr(module, "public_get_bytes", fake_public_get_bytes)

    summary = module.download_summary("octo/repo", 123, "behavior-benchmark-smoke-123", "token")

    assert json.loads(summary.decode("utf-8")) == {"ok": True}
    assert calls == [
        ("json", "https://api.github.com/repos/octo/repo/actions/runs/123/artifacts", "token"),
        ("redirect", "https://api.github.com/repos/octo/repo/actions/artifacts/42/zip", "token"),
        ("public-bytes", "https://example.invalid/artifact.zip"),
    ]
