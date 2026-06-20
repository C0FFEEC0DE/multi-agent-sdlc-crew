from reporter import render_metric, render_subtitle, render_title, render_warning


def test_render_title():
    assert render_title("  weekly status  ") == "WEEKLY STATUS"


def test_render_subtitle():
    assert render_subtitle("  system health  ") == "SYSTEM HEALTH"


def test_render_metric():
    assert render_metric(" latency ", 42) == "LATENCY: 42"


def test_render_warning():
    assert render_warning(" disk ", "high") == "WARNING DISK: high"

