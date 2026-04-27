from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from flow_engine.context.browser_session import (
    ActivityWatchBrowserSessionProvider,
    BrowserSessionContextPlugin,
    _AwEvent,
    infer_browser_session_signal,
    infer_last_browser_segment,
)


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


def _event(ts: datetime, duration: float, **data: object) -> _AwEvent:
    return _AwEvent(timestamp=ts, duration=duration, data=dict(data))


def test_infer_last_browser_segment_selects_most_recent_continuous_browser_segment() -> None:
    base = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    segment = infer_last_browser_segment(
        [
            _event(base - timedelta(minutes=20), 60, app="firefox.exe", title="old"),
            _event(base - timedelta(minutes=8), 60, app="Code.exe", title="editor"),
            _event(base - timedelta(minutes=6), 120, app="firefox.exe", title="page-a"),
            _event(base - timedelta(minutes=4), 120, app="firefox.exe", title="page-b"),
        ],
        lookback=timedelta(minutes=60),
        segment_gap=timedelta(seconds=5),
        reference_time=base,
    )

    assert segment is not None
    assert segment.app == "firefox.exe"
    assert segment.title == "page-b"
    assert segment.start == base - timedelta(minutes=6)


def test_infer_browser_session_signal_dedupes_and_caps_open_tabs() -> None:
    base = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    segment = infer_last_browser_segment(
        [_event(base - timedelta(minutes=10), 600, app="firefox.exe", title="Firefox")],
        lookback=timedelta(minutes=60),
        segment_gap=timedelta(seconds=5),
        reference_time=base,
    )
    assert segment is not None

    signal = infer_browser_session_signal(
        segment,
        [
            _event(base - timedelta(minutes=2), 10, url="https://active.example", tabCount=3),
            _event(base - timedelta(minutes=3), 10, url="https://docs.example", tabCount=3),
            _event(base - timedelta(minutes=4), 10, url="https://search.example", tabCount=3),
            _event(base - timedelta(minutes=5), 10, url="https://docs.example", tabCount=3),
            _event(base - timedelta(minutes=30), 10, url="https://outside.example", tabCount=3),
        ],
        max_pages=5,
    )

    assert signal is not None
    assert signal.active_url == "https://active.example"
    assert signal.recent_tabs == ["https://docs.example", "https://search.example"]
    assert signal.open_tabs == ["https://docs.example", "https://search.example"]
    assert signal.source == "derived_aw_last_browser_segment"


def test_infer_last_browser_segment_rejects_stale_browser_activity() -> None:
    base = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    segment = infer_last_browser_segment(
        [_event(base - timedelta(hours=2), 60, app="firefox.exe", title="stale")],
        lookback=timedelta(minutes=60),
        segment_gap=timedelta(seconds=5),
        reference_time=base,
    )

    assert segment is None


def test_activitywatch_browser_provider_returns_context_ready_signal(monkeypatch) -> None:
    base_url = "http://localhost:5600"
    base = datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
    responses = {
        (f"{base_url}/api/0/info", ()): {"hostname": "madejuele"},
        (f"{base_url}/api/0/buckets/", ()): {
            "aw-watcher-window_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T12:00:00+00:00",
            },
            "aw-watcher-web-firefox_madejuele": {
                "hostname": "madejuele",
                "last_updated": "2026-04-22T12:00:00+00:00",
            },
        },
        (
            f"{base_url}/api/0/buckets/aw-watcher-window_madejuele/events",
            (("limit", 100),),
        ): [
            {
                "timestamp": "2026-04-22T11:59:00+00:00",
                "duration": 60,
                "data": {"app": "firefox.exe", "title": "Firefox"},
            }
        ],
        (
            f"{base_url}/api/0/buckets/aw-watcher-web-firefox_madejuele/events",
            (("limit", 100),),
        ): [
            {
                "timestamp": "2026-04-22T11:59:50+00:00",
                "duration": 5,
                "data": {"url": "https://active.example", "tabCount": 2},
            },
            {
                "timestamp": "2026-04-22T11:59:20+00:00",
                "duration": 5,
                "data": {"url": "https://docs.example", "tabCount": 2},
            },
        ],
    }
    _install_fake_httpx(monkeypatch, responses)

    provider = ActivityWatchBrowserSessionProvider(base_url, clock=lambda: base)
    signal = asyncio.run(provider.current_session())

    assert signal is not None
    assert signal.active_url == "https://active.example"
    assert signal.open_tabs == ["https://docs.example"]

    plugin = BrowserSessionContextPlugin(provider)
    captured = asyncio.run(plugin.capture())
    assert captured["active_url"] == "https://active.example"
    assert captured["open_tabs"] == ["https://docs.example"]
    assert captured["recent_tabs"] == ["https://docs.example"]
    assert captured["browser_session_source"] == "derived_aw_last_browser_segment"


def test_activitywatch_browser_provider_degrades_when_aw_unavailable(monkeypatch) -> None:
    base_url = "http://localhost:5600"
    _install_fake_httpx(monkeypatch, {
        (f"{base_url}/api/0/buckets/", ()): RuntimeError("offline"),
    })

    provider = ActivityWatchBrowserSessionProvider(base_url)
    assert asyncio.run(provider.current_session()) is None
