from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

from flow_engine.context.aw_plugin import ActivityWatchPlugin


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> object:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, *, responses: dict[tuple[str, tuple[tuple[str, object], ...]], object], timeout: object) -> None:
        self._responses = responses
        self.timeout = timeout

    async def __aenter__(self) -> _FakeAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, params: dict[str, object] | None = None) -> _FakeResponse:
        key = (url, tuple(sorted((params or {}).items())))
        if key not in self._responses:
            raise AssertionError(f"unexpected request: {key!r}")
        response = self._responses[key]
        if isinstance(response, Exception):
            raise response
        return _FakeResponse(response)


def _install_fake_httpx(monkeypatch, responses: dict[tuple[str, tuple[tuple[str, object], ...]], object]) -> None:
    fake_httpx = SimpleNamespace(
        Timeout=lambda connect, read: {"connect": connect, "read": read},
        AsyncClient=lambda timeout: _FakeAsyncClient(responses=responses, timeout=timeout),
    )
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)


def test_capture_prefers_hostname_specific_web_bucket(monkeypatch) -> None:
    base_url = "http://localhost:5600"
    responses = {
        (f"{base_url}/api/0/info", ()): {"hostname": "madejuele"},
        (f"{base_url}/api/0/buckets/", ()): {
            "aw-watcher-web-firefox": {
                "hostname": "unknown",
                "last_updated": "2026-04-22T01:40:17.454000+00:00",
            },
            "aw-watcher-web-firefox_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:40:58.006000+00:00",
            },
            "aw-watcher-window_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:41:32.889000+00:00",
            },
        },
        (
            f"{base_url}/api/0/buckets/aw-watcher-window_madejuele/events",
            (("limit", 1),),
        ): [{"data": {"app": "firefox.exe", "title": "Mozilla Firefox"}}],
        (
            f"{base_url}/api/0/buckets/aw-watcher-web-firefox_madejuele/events",
            (("limit", 1),),
        ): [{"data": {"url": "https://example.com/real"}}],
    }
    _install_fake_httpx(monkeypatch, responses)

    plugin = ActivityWatchPlugin(base_url)
    captured = asyncio.run(plugin.capture())

    assert captured == {
        "active_window": "Mozilla Firefox",
        "active_url": "https://example.com/real",
    }


def test_capture_prefers_browser_matching_web_bucket_over_newer_other_browser(monkeypatch) -> None:
    base_url = "http://localhost:5600"
    responses = {
        (f"{base_url}/api/0/info", ()): {"hostname": "madejuele"},
        (f"{base_url}/api/0/buckets/", ()): {
            "aw-watcher-window_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:41:32.889000+00:00",
            },
            "aw-watcher-web-firefox_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:40:17.454000+00:00",
            },
            "aw-watcher-web-chrome_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:45:17.454000+00:00",
            },
        },
        (
            f"{base_url}/api/0/buckets/aw-watcher-window_madejuele/events",
            (("limit", 1),),
        ): [{"data": {"app": "firefox.exe", "title": "Mozilla Firefox"}}],
        (
            f"{base_url}/api/0/buckets/aw-watcher-web-firefox_madejuele/events",
            (("limit", 1),),
        ): [{"data": {"url": "https://example.com/firefox"}}],
    }
    _install_fake_httpx(monkeypatch, responses)

    plugin = ActivityWatchPlugin(base_url)
    captured = asyncio.run(plugin.capture())

    assert captured == {
        "active_window": "Mozilla Firefox",
        "active_url": "https://example.com/firefox",
    }


def test_capture_falls_back_without_info_endpoint(monkeypatch) -> None:
    base_url = "http://localhost:5600"
    responses = {
        (f"{base_url}/api/0/info", ()): RuntimeError("boom"),
        (f"{base_url}/api/0/buckets/", ()): {
            "aw-watcher-web-firefox_recent": {
                "hostname": "unknown",
                "last_updated": "2026-04-22T01:40:17.454000+00:00",
            },
        },
        (
            f"{base_url}/api/0/buckets/aw-watcher-web-firefox_recent/events",
            (("limit", 1),),
        ): [{"data": {"url": "https://example.com/latest"}}],
    }
    _install_fake_httpx(monkeypatch, responses)

    plugin = ActivityWatchPlugin(base_url)
    captured = asyncio.run(plugin.capture())

    assert captured == {"active_url": "https://example.com/latest"}


def test_capture_ignores_web_bucket_when_active_window_is_not_browser(monkeypatch) -> None:
    base_url = "http://localhost:5600"
    responses = {
        (f"{base_url}/api/0/info", ()): {"hostname": "madejuele"},
        (f"{base_url}/api/0/buckets/", ()): {
            "aw-watcher-window_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:41:32.889000+00:00",
            },
            "aw-watcher-web-firefox_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T01:45:17.454000+00:00",
            },
        },
        (
            f"{base_url}/api/0/buckets/aw-watcher-window_madejuele/events",
            (("limit", 1),),
        ): [{"data": {"app": "Antigravity.exe", "title": "flow workspace"}}],
    }
    _install_fake_httpx(monkeypatch, responses)

    plugin = ActivityWatchPlugin(base_url)
    captured = asyncio.run(plugin.capture())

    assert captured == {"active_window": "flow workspace"}
