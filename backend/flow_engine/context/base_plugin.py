"""上下文捕获插件抽象基类 + 快照管理.

Phase 5 升级：
- ContextPlugin 合约升级为全异步（async capture / async available）
- ContextService.capture_async 支持并发聚合多插件
- 快照序列化与反序列化保持纯同步（文件 I/O 由调用方选择线程化）
- 全部插件的外部调用由上层（app.py）决定走前台还是后台队列

设计要点：
- ContextPlugin 是所有捕获插件的合约（ActivityWatch、自定义等）。
- SnapshotManager 负责序列化/反序列化，不关心数据来源。
- ContextService 是外部调用的唯一入口，聚合多个插件。
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from flow_engine.context.trail import TrailCollector, TrailEvent, TrailStore

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 快照数据结构
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """桌面现场快照."""

    task_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    schema_version: int = 3
    active_window: str = ""
    active_url: str = ""
    active_file: str = ""
    active_workspace: str = ""
    open_windows: list[str] = field(default_factory=list)
    open_tabs: list[str] = field(default_factory=list)
    recent_tabs: list[str] = field(default_factory=list)
    open_files: list[str] = field(default_factory=list)
    source_plugin: str = ""
    capture_trigger: str = ""
    session_duration_sec: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def build(task_id: int, raw: dict[str, Any]) -> Snapshot:
        """从插件聚合的原始字典构建快照（工厂方法）.

        自动提取已知核心字段，将剩余字段归入 extra。
        新增核心字段时只需修改此方法，外部调用方无感。
        """
        data = dict(raw)  # 浅拷贝，避免破坏调用方的数据
        data.pop("schema_version", None)
        return Snapshot(
            task_id=task_id,
            schema_version=3,
            active_window=data.pop("active_window", ""),
            active_url=data.pop("active_url", ""),
            active_file=data.pop("active_file", ""),
            active_workspace=data.pop("active_workspace", ""),
            open_windows=_coerce_list(data.pop("open_windows", [])),
            open_tabs=_coerce_list(data.pop("open_tabs", [])),
            recent_tabs=_coerce_list(data.pop("recent_tabs", [])),
            open_files=_coerce_list(data.pop("open_files", [])),
            source_plugin=data.pop("source_plugin", ""),
            capture_trigger=data.pop("capture_trigger", ""),
            session_duration_sec=int(data.pop("session_duration_sec", 0) or 0),
            extra=data,
        )


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if value in (None, ""):
        return []
    return [str(value)]


def _coerce_plugin_tokens(value: Any) -> list[str]:
    if isinstance(value, list):
        raw_items = value
    elif value in (None, ""):
        raw_items = []
    else:
        raw_items = str(value).split(",")
    return [str(item).strip() for item in raw_items if str(item).strip()]


def _merge_source_plugins(contributors: list[str], raw_value: Any) -> str:
    ordered: list[str] = []
    seen: set[str] = set()
    for token in [*contributors, *_coerce_plugin_tokens(raw_value)]:
        if token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ",".join(ordered)


# ---------------------------------------------------------------------------
# 插件抽象基类 — 全异步合约
# ---------------------------------------------------------------------------

class ContextPlugin(ABC):
    """上下文捕获插件合约.

    Phase 5 升级：所有方法升级为 async，消除同步 I/O 阻塞主事件循环。

    所有插件必须实现：
    - name: 插件标识符
    - capture: 异步捕获当前桌面上下文
    - available: 异步检测插件是否可用
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """插件标识名."""

    @abstractmethod
    async def available(self) -> bool:
        """异步检测插件是否可用（依赖服务是否在线等）."""

    @abstractmethod
    async def capture(self) -> dict[str, Any]:
        """异步捕获当前上下文，返回键值对数据.

        Returns:
            插件捕获的数据字典，至少可包含 active_window / active_url。
        """


# ---------------------------------------------------------------------------
# 快照持久化
# ---------------------------------------------------------------------------

class SnapshotManager:
    """快照的序列化与反序列化.

    纯文件 I/O，保持同步。调用方可自行决定用 asyncio.to_thread 包裹。
    """

    def __init__(self, snapshots_dir: Path) -> None:
        self._dir = snapshots_dir

    def save(self, snapshot: Snapshot) -> Path:
        """将快照写入 JSON 文件，返回文件路径."""
        task_dir = self._dir / str(snapshot.task_id)
        task_dir.mkdir(parents=True, exist_ok=True)

        filename = snapshot.timestamp.strftime("%Y%m%d_%H%M%S") + ".json"
        path = task_dir / filename

        data = asdict(snapshot)
        data["timestamp"] = snapshot.timestamp.isoformat()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.debug("snapshot saved: %s", path)
        return path

    def load_latest(self, task_id: int) -> Snapshot | None:
        """加载某任务最新的快照."""
        task_dir = self._dir / str(task_id)
        if not task_dir.exists():
            return None

        files = sorted(task_dir.glob("*.json"), reverse=True)
        if not files:
            return None

        data = json.loads(files[0].read_text(encoding="utf-8"))
        schema_version = int(data.get("schema_version", 1))
        return Snapshot(
            task_id=data["task_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            schema_version=schema_version,
            active_window=data.get("active_window", ""),
            active_url=data.get("active_url", ""),
            active_file=data.get("active_file", ""),
            active_workspace=data.get("active_workspace", ""),
            open_windows=_coerce_list(data.get("open_windows", [])),
            open_tabs=_coerce_list(data.get("open_tabs", [])),
            recent_tabs=_coerce_list(data.get("recent_tabs", [])),
            open_files=_coerce_list(data.get("open_files", [])),
            source_plugin=data.get("source_plugin", ""),
            capture_trigger=data.get("capture_trigger", ""),
            session_duration_sec=int(data.get("session_duration_sec", 0) or 0),
            extra=data.get("extra", {}),
        )


# ---------------------------------------------------------------------------
# 上下文服务 — 聚合多个异步插件
# ---------------------------------------------------------------------------

class ContextService:
    """物理层对外的唯一服务接口.

    聚合所有已注册的异步插件，并发捕获结果后合并。

    Phase 5 变更：
    - capture_async() 替代旧同步 capture()，全流程不阻塞
    - 每个插件的 capture 互相隔离，单一插件爆炸不影响其余
    - 快照保存委托给 asyncio.to_thread，解放事件循环

    用法:
        svc = ContextService(snapshot_mgr)
        svc.register(AWPlugin(...))
        snapshot = await svc.capture_async(task_id=1)
    """

    def __init__(
        self,
        snapshot_manager: SnapshotManager,
        *,
        trail_store: TrailStore | None = None,
    ) -> None:
        self._manager = snapshot_manager
        self._trail_store = trail_store
        self._plugins: list[ContextPlugin] = []
        self._collectors: list[TrailCollector] = []

    def register(self, plugin: ContextPlugin) -> None:
        """注册一个捕获插件."""
        self._plugins.append(plugin)
        logger.info("context plugin registered: %s", plugin.name)

    def register_collector(self, collector: TrailCollector) -> None:
        self._collectors.append(collector)
        logger.info("trail collector registered: %s", collector.source_name)

    async def capture_async(self, task_id: int, *, capture_trigger: str = "") -> Snapshot:
        """并发聚合所有可用插件的捕获结果，返回合并的快照.

        每个插件互相隔离执行，单个失败不影响其余。
        """
        merged: dict[str, Any] = {}
        contributors: list[str] = []

        async def _try_capture(plugin: ContextPlugin) -> tuple[str, dict[str, Any]]:
            """安全地尝试捕获单个插件的上下文."""
            try:
                if await plugin.available():
                    return plugin.name, await plugin.capture()
            except Exception:
                logger.exception("plugin %s capture failed", plugin.name)
            return plugin.name, {}

        # 全部插件并发执行，互不阻塞
        results = await asyncio.gather(
            *[_try_capture(p) for p in self._plugins],
        )
        for plugin_name, data in results:
            if data:
                contributors.append(plugin_name)
            merged.update(data)
        normalized_sources = _merge_source_plugins(contributors, merged.get("source_plugin"))
        if normalized_sources:
            merged["source_plugin"] = normalized_sources
        if capture_trigger:
            merged["capture_trigger"] = capture_trigger

        snapshot = Snapshot.build(task_id, merged)
        await self._write_trails(task_id, snapshot)
        # 快照落盘走线程池，不阻塞事件循环
        await asyncio.to_thread(self._manager.save, snapshot)
        return snapshot

    def restore_latest(self, task_id: int) -> Snapshot | None:
        """恢复某任务最新保存的快照."""
        return self._manager.load_latest(task_id)

    async def _write_trails(self, task_id: int, snapshot: Snapshot) -> None:
        if self._trail_store is None or not self._collectors:
            return

        events: list[TrailEvent] = []
        for collector in self._collectors:
            try:
                events.extend(await collector.collect(task_id, snapshot))
            except Exception:
                logger.exception("trail collector %s failed", collector.source_name)

        if not events:
            return

        try:
            await asyncio.to_thread(self._append_trails, events)
        except Exception:
            logger.exception("trail write failed for task #%s", task_id)

    def _append_trails(self, events: list[TrailEvent]) -> None:
        if self._trail_store is None:
            return
        for event in events:
            self._trail_store.append(event)
