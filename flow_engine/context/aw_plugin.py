"""ActivityWatch 插件 — ContextPlugin 的首个实现.

通过 HTTP 调用本地 ActivityWatch REST API 获取当前活跃窗口和浏览器 URL。
如果 AW 未运行，available() 返回 False，系统静默跳过。
"""

from __future__ import annotations

import logging
from typing import Any

from flow_engine.context.base_plugin import ContextPlugin

logger = logging.getLogger(__name__)


class ActivityWatchPlugin(ContextPlugin):
    """ActivityWatch 上下文捕获插件."""

    def __init__(self, base_url: str = "http://localhost:5600") -> None:
        self._base_url = base_url.rstrip("/")

    @property
    def name(self) -> str:
        return "activitywatch"

    def available(self) -> bool:
        """检测 AW 是否在本地运行."""
        try:
            import httpx

            resp = httpx.get(f"{self._base_url}/api/0/info", timeout=2.0)
            return resp.status_code == 200
        except Exception:
            return False

    def capture(self) -> dict[str, Any]:
        """从 AW API 获取当前窗口和 URL.

        Returns:
            {"active_window": "...", "active_url": "...", ...}
        """
        import httpx

        result: dict[str, Any] = {}

        # 获取可用的 bucket 列表
        try:
            resp = httpx.get(f"{self._base_url}/api/0/buckets", timeout=5.0)
            buckets = resp.json()
        except Exception:
            logger.warning("failed to fetch AW buckets")
            return result

        # 从 aw-watcher-window bucket 获取活跃窗口
        for bucket_id in buckets:
            if "aw-watcher-window" in bucket_id:
                try:
                    resp = httpx.get(
                        f"{self._base_url}/api/0/buckets/{bucket_id}/events",
                        params={"limit": 1},
                        timeout=5.0,
                    )
                    events = resp.json()
                    if events:
                        data = events[0].get("data", {})
                        result["active_window"] = data.get("title", "")
                except Exception:
                    logger.warning("failed to fetch window events from %s", bucket_id)

            # 从 aw-watcher-web bucket 获取当前 URL
            if "aw-watcher-web" in bucket_id:
                try:
                    resp = httpx.get(
                        f"{self._base_url}/api/0/buckets/{bucket_id}/events",
                        params={"limit": 1},
                        timeout=5.0,
                    )
                    events = resp.json()
                    if events:
                        data = events[0].get("data", {})
                        result["active_url"] = data.get("url", "")
                except Exception:
                    logger.warning("failed to fetch web events from %s", bucket_id)

        return result
