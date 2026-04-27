"""Browser session signal providers and ActivityWatch-backed inference."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

from flow_engine.context.base_plugin import ContextPlugin

logger = logging.getLogger(__name__)

_AW_CONNECT_TIMEOUT = 1.0
_AW_READ_TIMEOUT = 3.0
_DEFAULT_EVENT_LIMIT = 100
DERIVED_AW_LAST_BROWSER_SEGMENT = "derived_aw_last_browser_segment"


@dataclass(frozen=True)
class BrowserSessionSignal:
    """Flow-owned browser session semantics, independent from provider wire shape."""

    active_url: str = ""
    open_tabs: list[str] = field(default_factory=list)
    recent_tabs: list[str] = field(default_factory=list)
    tab_count: int | None = None
    source: str = DERIVED_AW_LAST_BROWSER_SEGMENT
    browser_app: str = ""
    browser_title: str = ""
    segment_start: datetime | None = None
    segment_end: datetime | None = None

    def to_context_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "source_plugin": "browser-session",
            "browser_session_source": self.source,
        }
        if self.active_url:
            data["active_url"] = self.active_url
        if self.open_tabs:
            data["open_tabs"] = list(self.open_tabs)
        if self.recent_tabs:
            data["recent_tabs"] = list(self.recent_tabs)
        if self.tab_count is not None:
            data["browser_tab_count"] = self.tab_count
        if self.browser_app:
            data["browser_app"] = self.browser_app
        if self.browser_title:
            data["browser_title"] = self.browser_title
        if self.segment_start is not None:
            data["browser_segment_start"] = self.segment_start.isoformat()
        if self.segment_end is not None:
            data["browser_segment_end"] = self.segment_end.isoformat()
        return data


class BrowserSessionProvider(ABC):
    """Provider boundary for browser session signals."""

    @abstractmethod
    async def available(self) -> bool:
        """Return whether the provider can be queried."""

    @abstractmethod
    async def current_session(self) -> BrowserSessionSignal | None:
        """Return the latest bounded browser session signal, if available."""


class BrowserSessionContextPlugin(ContextPlugin):
    """Adapt a browser session provider into the generic context plugin contract."""

    def __init__(self, provider: BrowserSessionProvider) -> None:
        self._provider = provider

    @property
    def name(self) -> str:
        return "browser-session"

    async def available(self) -> bool:
        return await self._provider.available()

    async def capture(self) -> dict[str, Any]:
        signal = await self._provider.current_session()
        if signal is None:
            return {}
        return signal.to_context_dict()


@dataclass(frozen=True)
class _AwEvent:
    timestamp: datetime
    duration: float
    data: dict[str, Any]

    @property
    def end(self) -> datetime:
        return self.timestamp + timedelta(seconds=max(0.0, self.duration))


@dataclass(frozen=True)
class _BrowserSegment:
    start: datetime
    end: datetime
    app: str
    title: str


class ActivityWatchBrowserSessionProvider(BrowserSessionProvider):
    """Infer a bounded browser session from ActivityWatch window and web events."""

    def __init__(
        self,
        base_url: str = "http://localhost:5600",
        *,
        max_pages: int = 5,
        lookback_minutes: int = 60,
        segment_gap_seconds: int = 5,
        event_limit: int = _DEFAULT_EVENT_LIMIT,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_pages = max(1, int(max_pages))
        self._lookback = timedelta(minutes=max(1, int(lookback_minutes)))
        self._segment_gap = timedelta(seconds=max(0, int(segment_gap_seconds)))
        self._event_limit = max(1, int(event_limit))
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    async def available(self) -> bool:
        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(_AW_CONNECT_TIMEOUT, read=_AW_READ_TIMEOUT),
            ) as client:
                resp = await client.get(f"{self._base_url}/api/0/info")
                return resp.status_code == 200
        except Exception:
            return False

    async def current_session(self) -> BrowserSessionSignal | None:
        try:
            import httpx

            timeout = httpx.Timeout(_AW_CONNECT_TIMEOUT, read=_AW_READ_TIMEOUT)
            async with httpx.AsyncClient(timeout=timeout) as client:
                reference_time = _as_utc(self._clock())
                buckets = await self._fetch_buckets(client)
                preferred_hostname = await self._get_preferred_hostname(client)
                window_bucket = self._select_bucket_id(
                    buckets,
                    "aw-watcher-window",
                    preferred_hostname,
                )
                if not window_bucket:
                    return None

                window_events = await self._fetch_events(client, window_bucket)
                segment = infer_last_browser_segment(
                    window_events,
                    lookback=self._lookback,
                    segment_gap=self._segment_gap,
                    reference_time=reference_time,
                )
                if segment is None:
                    return None

                web_bucket = self._select_bucket_id(
                    buckets,
                    "aw-watcher-web",
                    preferred_hostname,
                    browser_hints=_browser_hints_from_app(segment.app),
                )
                if not web_bucket:
                    return None

                web_events = await self._fetch_events(client, web_bucket)
                return infer_browser_session_signal(
                    segment,
                    web_events,
                    max_pages=self._max_pages,
                )
        except Exception:
            logger.debug("ActivityWatch browser session inference failed", exc_info=True)
            return None

    async def _fetch_buckets(self, client: Any) -> dict[str, Any]:
        resp = await client.get(f"{self._base_url}/api/0/buckets/")
        buckets = resp.json()
        return buckets if isinstance(buckets, dict) else {}

    async def _get_preferred_hostname(self, client: Any) -> str:
        try:
            resp = await client.get(f"{self._base_url}/api/0/info")
            info = resp.json()
            return str(info.get("hostname", "")).strip() if isinstance(info, dict) else ""
        except Exception:
            return ""

    def _select_bucket_id(
        self,
        buckets: dict[str, Any],
        watcher_prefix: str,
        preferred_hostname: str,
        *,
        browser_hints: tuple[str, ...] = (),
    ) -> str | None:
        matches = [
            (bucket_id, meta)
            for bucket_id, meta in buckets.items()
            if watcher_prefix in bucket_id
        ]
        if not matches:
            return None

        def rank(item: tuple[str, Any]) -> tuple[int, int, datetime]:
            bucket_id, meta = item
            metadata = meta if isinstance(meta, dict) else {}
            hostname = str(metadata.get("hostname", "")).strip()
            updated_at = _parse_time(str(metadata.get("last_updated") or metadata.get("created") or ""))
            bucket_lower = bucket_id.lower()
            return (
                1 if browser_hints and any(hint in bucket_lower for hint in browser_hints) else 0,
                1 if preferred_hostname and hostname == preferred_hostname else 0,
                updated_at,
            )

        return max(matches, key=rank)[0]

    async def _fetch_events(self, client: Any, bucket_id: str) -> list[_AwEvent]:
        encoded_bucket = quote(bucket_id, safe="")
        resp = await client.get(
            f"{self._base_url}/api/0/buckets/{encoded_bucket}/events",
            params={"limit": self._event_limit},
        )
        raw_events = resp.json()
        if not isinstance(raw_events, list):
            return []
        events = [_event_from_raw(raw) for raw in raw_events if isinstance(raw, dict)]
        return [event for event in events if event is not None]


def infer_last_browser_segment(
    window_events: list[_AwEvent],
    *,
    lookback: timedelta,
    segment_gap: timedelta,
    reference_time: datetime | None = None,
) -> _BrowserSegment | None:
    """Select the latest continuous browser foreground segment from AW window events."""

    cutoff = _as_utc(reference_time or datetime.now(timezone.utc)) - lookback
    events = sorted(
        (event for event in window_events if event.end >= cutoff),
        key=lambda event: event.timestamp,
        reverse=True,
    )
    if not events:
        return None

    selected: list[_AwEvent] = []
    previous_start: datetime | None = None

    for event in events:
        app = str(event.data.get("app", "")).strip()
        if not _is_browser_app(app):
            if selected:
                break
            continue
        if previous_start is not None and event.end + segment_gap < previous_start:
            break
        selected.append(event)
        previous_start = event.timestamp

    if not selected:
        return None

    latest = max(selected, key=lambda event: event.end)
    return _BrowserSegment(
        start=min(event.timestamp for event in selected),
        end=max(event.end for event in selected),
        app=str(latest.data.get("app", "")).strip(),
        title=str(latest.data.get("title", "")).strip(),
    )


def infer_browser_session_signal(
    segment: _BrowserSegment,
    web_events: list[_AwEvent],
    *,
    max_pages: int,
) -> BrowserSessionSignal | None:
    """Infer active/recent/open URL sets from web events inside a browser segment."""

    in_segment = [
        event
        for event in web_events
        if _event_overlaps(event, segment.start, segment.end)
        and str(event.data.get("url", "")).strip()
    ]
    if not in_segment:
        return None

    by_recent = sorted(in_segment, key=lambda event: event.timestamp, reverse=True)
    active_event = by_recent[0]
    active_url = str(active_event.data.get("url", "")).strip()
    if not active_url:
        return None

    recent_tabs: list[str] = []
    seen = {active_url}
    for event in by_recent[1:]:
        url = str(event.data.get("url", "")).strip()
        if not url or url in seen:
            continue
        seen.add(url)
        recent_tabs.append(url)

    tab_count = _coerce_optional_int(active_event.data.get("tabCount"))
    if tab_count is None:
        page_limit = max_pages
    else:
        page_limit = min(max_pages, max(1, tab_count))
    open_tab_limit = max(0, page_limit - 1)
    open_tabs = recent_tabs[:open_tab_limit]

    return BrowserSessionSignal(
        active_url=active_url,
        open_tabs=open_tabs,
        recent_tabs=recent_tabs,
        tab_count=tab_count,
        browser_app=segment.app,
        browser_title=segment.title,
        segment_start=segment.start,
        segment_end=segment.end,
    )


def _event_from_raw(raw: dict[str, Any]) -> _AwEvent | None:
    timestamp = _parse_time(str(raw.get("timestamp", "")))
    if timestamp == datetime.min:
        return None
    data = raw.get("data", {})
    return _AwEvent(
        timestamp=timestamp,
        duration=_coerce_float(raw.get("duration")),
        data=data if isinstance(data, dict) else {},
    )


def _parse_time(raw: str) -> datetime:
    if not raw:
        return datetime.min
    normalized = raw.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.min
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _event_overlaps(event: _AwEvent, start: datetime, end: datetime) -> bool:
    return event.timestamp <= end and event.end >= start


def _coerce_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _coerce_optional_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _is_browser_app(app: str) -> bool:
    app_lower = app.lower()
    return any(hint in app_lower for hint in ("firefox", "chrome", "msedge", "edge", "brave", "opera", "arc", "chromium"))


def _browser_hints_from_app(app: str) -> tuple[str, ...]:
    app_lower = app.lower()
    if "firefox" in app_lower:
        return ("firefox",)
    if "msedge" in app_lower or "edge" in app_lower:
        return ("edge", "chrome")
    if "brave" in app_lower:
        return ("brave", "chrome")
    if "opera" in app_lower:
        return ("opera", "chrome")
    if "arc" in app_lower:
        return ("arc", "chrome")
    if "chromium" in app_lower:
        return ("chromium", "chrome")
    if "chrome" in app_lower:
        return ("chrome",)
    return ()
