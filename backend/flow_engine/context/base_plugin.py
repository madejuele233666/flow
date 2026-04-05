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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 快照数据结构
# ---------------------------------------------------------------------------

@dataclass
class Snapshot:
    """桌面现场快照."""

    task_id: int
    timestamp: datetime = field(default_factory=datetime.now)
    active_window: str = ""
    active_url: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def build(task_id: int, raw: dict[str, Any]) -> Snapshot:
        """从插件聚合的原始字典构建快照（工厂方法）.

        自动提取已知核心字段，将剩余字段归入 extra。
        新增核心字段时只需修改此方法，外部调用方无感。
        """
        data = dict(raw)  # 浅拷贝，避免破坏调用方的数据
        return Snapshot(
            task_id=task_id,
            active_window=data.pop("active_window", ""),
            active_url=data.pop("active_url", ""),
            extra=data,
        )


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
        return Snapshot(
            task_id=data["task_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            active_window=data.get("active_window", ""),
            active_url=data.get("active_url", ""),
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

    def __init__(self, snapshot_manager: SnapshotManager) -> None:
        self._manager = snapshot_manager
        self._plugins: list[ContextPlugin] = []

    def register(self, plugin: ContextPlugin) -> None:
        """注册一个捕获插件."""
        self._plugins.append(plugin)
        logger.info("context plugin registered: %s", plugin.name)

    async def capture_async(self, task_id: int) -> Snapshot:
        """并发聚合所有可用插件的捕获结果，返回合并的快照.

        每个插件互相隔离执行，单个失败不影响其余。
        """
        merged: dict[str, Any] = {}

        async def _try_capture(plugin: ContextPlugin) -> dict[str, Any]:
            """安全地尝试捕获单个插件的上下文."""
            try:
                if await plugin.available():
                    return await plugin.capture()
            except Exception:
                logger.exception("plugin %s capture failed", plugin.name)
            return {}

        # 全部插件并发执行，互不阻塞
        results = await asyncio.gather(
            *[_try_capture(p) for p in self._plugins],
        )
        for data in results:
            merged.update(data)

        snapshot = Snapshot.build(task_id, merged)
        # 快照落盘走线程池，不阻塞事件循环
        await asyncio.to_thread(self._manager.save, snapshot)
        return snapshot

    def restore_latest(self, task_id: int) -> Snapshot | None:
        """恢复某任务最新保存的快照."""
        return self._manager.load_latest(task_id)
