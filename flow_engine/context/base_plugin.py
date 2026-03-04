"""上下文捕获插件抽象基类 + 快照管理.

设计要点：
- ContextPlugin 是所有捕获插件的合约（ActivityWatch、自定义等）。
- SnapshotManager 负责序列化/反序列化，不关心数据来源。
- ContextService 是外部调用的唯一入口，聚合多个插件。
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# 插件抽象基类
# ---------------------------------------------------------------------------

class ContextPlugin(ABC):
    """上下文捕获插件合约.

    所有插件必须实现：
    - name: 插件标识符
    - capture: 捕获当前桌面上下文
    - available: 检测插件是否可用（如 ActivityWatch 是否在运行）
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """插件标识名."""

    @abstractmethod
    def available(self) -> bool:
        """检测插件是否可用（依赖服务是否在线等）."""

    @abstractmethod
    def capture(self) -> dict[str, Any]:
        """捕获当前上下文，返回键值对数据.

        Returns:
            插件捕获的数据字典，至少可包含 active_window / active_url。
        """


# ---------------------------------------------------------------------------
# 快照持久化
# ---------------------------------------------------------------------------

class SnapshotManager:
    """快照的序列化与反序列化."""

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
# 上下文服务 — 聚合多个插件
# ---------------------------------------------------------------------------

class ContextService:
    """物理层对外的唯一服务接口.

    聚合所有已注册的插件，按优先级合并捕获结果。

    用法:
        svc = ContextService(snapshot_mgr)
        svc.register(AWPlugin(...))
        svc.register(MyCustomPlugin(...))
        snapshot = svc.capture(task_id=1)
    """

    def __init__(self, snapshot_manager: SnapshotManager) -> None:
        self._manager = snapshot_manager
        self._plugins: list[ContextPlugin] = []

    def register(self, plugin: ContextPlugin) -> None:
        """注册一个捕获插件."""
        self._plugins.append(plugin)
        logger.info("context plugin registered: %s", plugin.name)

    def capture(self, task_id: int) -> Snapshot:
        """聚合所有可用插件的捕获结果，返回合并的快照."""
        merged: dict[str, Any] = {}
        for plugin in self._plugins:
            if plugin.available():
                try:
                    data = plugin.capture()
                    merged.update(data)
                except Exception:
                    logger.exception("plugin %s capture failed", plugin.name)

        snapshot = Snapshot(
            task_id=task_id,
            active_window=merged.pop("active_window", ""),
            active_url=merged.pop("active_url", ""),
            extra=merged,  # 剩余字段全部归入 extra
        )
        self._manager.save(snapshot)
        return snapshot

    def restore_latest(self, task_id: int) -> Snapshot | None:
        """恢复某任务最新保存的快照."""
        return self._manager.load_latest(task_id)
