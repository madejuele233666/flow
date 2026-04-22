"""ActivityWatch 插件 — ContextPlugin 的首个实现.

Phase 5 升级：
- 全异步 HTTP 调用（httpx.AsyncClient）
- 内置请求级熔断器 — AW 未运行时静默降级，绝不阻塞
- 纯 API 消费者角色 — 不做任何驻留式监听，只在被调用时单次查询
- 所有超时/重试由调用方（BackgroundEventWorker）控制

设计要点：
- 不持有任何长连接或轮询循环
- available() 和 capture() 均为 async，调用方可并发聚合
- 即使 AW 完全离线，也只 return {} 静默降级
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from flow_engine.context.base_plugin import ContextPlugin, Snapshot
from flow_engine.context.trail import TrailCollector, TrailEvent

logger = logging.getLogger(__name__)

# HTTP 超时（秒）— 宁可快速放弃也不阻塞主流程
_AW_CONNECT_TIMEOUT = 1.0
_AW_READ_TIMEOUT = 3.0


class ActivityWatchPlugin(ContextPlugin):
    """ActivityWatch 上下文捕获插件（纯异步，零阻塞）.

    职责边界：
    ✅ 在被上层调用时，向本地 aw-server 发起单次 REST 查询
    ❌ 不做窗口监听（那是 aw-watcher-window 的事）
    ❌ 不做 AFK 检测（那是 aw-watcher-afk 的事）
    ❌ 不做浏览器监听（那是 aw-watcher-web 的事）
    """

    def __init__(self, base_url: str = "http://localhost:5600") -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "activitywatch"

    async def available(self) -> bool:
        """异步检测 AW 是否在本地运行."""
        try:
            import httpx

            async with httpx.AsyncClient(
                timeout=httpx.Timeout(_AW_CONNECT_TIMEOUT, read=_AW_READ_TIMEOUT),
            ) as client:
                resp = await client.get(f"{self._base_url}/api/0/info")
                return resp.status_code == 200
        except Exception:
            return False

    async def capture(self) -> dict[str, Any]:
        """从 AW API 获取当前窗口和 URL.

        Returns:
            {"active_window": "...", "active_url": "...", ...}
            若 AW 不可用或请求失败，返回空 dict（静默降级）。
        """
        import httpx

        result: dict[str, Any] = {}
        timeout = httpx.Timeout(_AW_CONNECT_TIMEOUT, read=_AW_READ_TIMEOUT)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 1. 获取 bucket 列表
                resp = await client.get(f"{self._base_url}/api/0/buckets/")
                buckets = resp.json()

                preferred_hostname = await self._get_preferred_hostname(client)
                window_bucket = self._select_bucket_id(
                    buckets,
                    "aw-watcher-window",
                    preferred_hostname,
                )

                if window_bucket:
                    window_event = await self._fetch_latest_event(client, window_bucket)
                    active_window = str(window_event.get("data", {}).get("title", "")).strip()
                    if active_window:
                        result["active_window"] = active_window

                    if window_event:
                        browser_hints: tuple[str, ...] | None = self._browser_hints_from_window_event(window_event)
                    else:
                        browser_hints = None
                else:
                    browser_hints = None

                web_bucket = None
                if browser_hints is None:
                    web_bucket = self._select_bucket_id(
                        buckets,
                        "aw-watcher-web",
                        preferred_hostname,
                    )
                elif browser_hints:
                    web_bucket = self._select_bucket_id(
                        buckets,
                        "aw-watcher-web",
                        preferred_hostname,
                        browser_hints=browser_hints,
                    )
                if web_bucket:
                    result.update(
                        await self._fetch_latest(client, web_bucket, "active_url", "url"),
                    )
        except Exception:
            # 完全静默 — AW 离线不应该影响心流引擎的任何核心功能
            logger.debug("AW unreachable, skipping context capture")

        return result

    async def _get_preferred_hostname(self, client: Any) -> str:
        try:
            resp = await client.get(f"{self._base_url}/api/0/info")
            info = resp.json()
            return str(info.get("hostname", "")).strip()
        except Exception:
            logger.debug("failed to fetch AW hostname, continuing without host hint")
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
            updated_at = self._parse_bucket_time(
                str(metadata.get("last_updated") or metadata.get("created") or ""),
            )
            bucket_lower = bucket_id.lower()
            return (
                1 if browser_hints and any(hint in bucket_lower for hint in browser_hints) else 0,
                1 if preferred_hostname and hostname == preferred_hostname else 0,
                updated_at,
            )

        return max(matches, key=rank)[0]

    def _browser_hints_from_window_event(self, event: dict[str, Any]) -> tuple[str, ...]:
        app = str(event.get("data", {}).get("app", "")).strip().lower()
        if not app:
            return ()

        hints = {
            "firefox.exe": ("firefox",),
            "chrome.exe": ("chrome",),
            "brave.exe": ("brave", "chrome"),
            "opera.exe": ("opera", "chrome"),
            "msedge.exe": ("chrome", "edge"),
            "arc.exe": ("chrome", "arc"),
            "chromium.exe": ("chromium", "chrome"),
        }.get(app, ())
        return hints

    def _parse_bucket_time(self, raw: str) -> datetime:
        if not raw:
            return datetime.min
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return datetime.min

    async def _fetch_latest_event(
        self,
        client: Any,
        bucket_id: str,
    ) -> dict[str, Any]:
        try:
            resp = await client.get(
                f"{self._base_url}/api/0/buckets/{bucket_id}/events",
                params={"limit": 1},
            )
            events = resp.json()
            if events:
                first = events[0]
                return first if isinstance(first, dict) else {}
        except Exception:
            logger.debug("failed to fetch latest event from bucket %s", bucket_id)
        return {}

    async def _fetch_latest(
        self,
        client: Any,
        bucket_id: str,
        target_key: str,
        source_field: str,
    ) -> dict[str, str]:
        """从指定 bucket 获取最新一条事件的指定字段."""
        try:
            event = await self._fetch_latest_event(client, bucket_id)
            value = str(event.get("data", {}).get(source_field, "")).strip()
            if value:
                return {target_key: value}
        except Exception:
            logger.debug("failed to fetch from bucket %s", bucket_id)
        return {}


class ActivityWatchTrailCollector(TrailCollector):
    """Translate captured AW snapshot fields into passive trail events."""

    @property
    def source_name(self) -> str:
        return "activitywatch"

    async def collect(self, task_id: int, snapshot: Snapshot) -> list[TrailEvent]:
        sources = {item.strip() for item in snapshot.source_plugin.split(",") if item.strip()}
        if sources and self.source_name not in sources:
            return []

        events: list[TrailEvent] = []
        now = snapshot.timestamp if snapshot.timestamp else datetime.now()
        if snapshot.active_window:
            events.append(TrailEvent(
                task_id=task_id,
                timestamp=now,
                source=self.source_name,
                event_type="window_focus",
                summary=snapshot.active_window,
                metadata={"active_window": snapshot.active_window},
            ))
        if snapshot.active_url:
            events.append(TrailEvent(
                task_id=task_id,
                timestamp=now,
                source=self.source_name,
                event_type="url_visit",
                summary=snapshot.active_url,
                metadata={"active_url": snapshot.active_url},
            ))
        return events
