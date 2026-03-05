"""FlowClient — 六边形架构的 Primary Port.

设计来源：
- Docker SDK: docker.from_env() 返回 DockerClient，CLI 和 SDK 共用同一接口
- systemd: systemctl 通过 D-Bus 与 systemd daemon 通信，CLI 只是薄封装
- Hexagonal Architecture (Ports & Adapters): 表现层通过端口契约与领域层交互

目的：
CLI、TUI 和第三方插件统一依赖此 Protocol，而非裸露的 FlowApp 或 IPCClient。
LocalClient 直连内核（Daemon 关闭时），RemoteClient 走 IPC（Daemon 运行时）。
两个适配器对调用方完全透明。

用法：
    client = create_client()       # 自动探测模式
    result = await client.add_task(title="foo", priority=1)
    tasks  = await client.list_tasks()
    await client.start_task(task_id=3)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FlowClient Protocol — 端口契约
# ---------------------------------------------------------------------------

@runtime_checkable
class FlowClient(Protocol):
    """CLI / TUI / Plugin 与 Flow Engine 交互的唯一契约.

    所有方法返回纯 dict 或 list[dict]，不暴露领域对象。
    这确保了 RPC 序列化安全性与表现层解耦。
    """

    async def add_task(
        self,
        title: str,
        priority: int = 2,
        ddl: str | None = None,
        tags: list[str] | None = None,
        template_name: str | None = None,
    ) -> dict[str, Any]:
        """添加任务，返回 {id, title, ...}."""
        ...

    async def list_tasks(
        self,
        show_all: bool = False,
        filter_state: str | None = None,
        filter_tag: str | None = None,
        filter_priority: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出任务（按引力排序），返回 [{id, title, state, priority, score}, ...]."""
        ...

    async def start_task(self, task_id: int) -> dict[str, Any]:
        """开始任务，返回 {id, title, paused: [int, ...]}."""
        ...

    async def done_task(self) -> dict[str, Any]:
        """完成当前活跃任务，返回 {id, title}."""
        ...

    async def pause_task(self) -> dict[str, Any]:
        """暂停当前活跃任务，返回 {id, title}."""
        ...

    async def resume_task(self, task_id: int) -> dict[str, Any]:
        """恢复任务，返回 {id, title, state}."""
        ...

    async def block_task(self, task_id: int, reason: str = "") -> dict[str, Any]:
        """阻塞任务，返回 {id, title, reason}."""
        ...

    async def get_status(self) -> dict[str, Any]:
        """查询活跃任务状态，返回 {active: {id, title, priority, ...} | None}."""
        ...

    async def breakdown_task(self, task_id: int) -> list[str]:
        """AI 拆解任务，返回步骤列表."""
        ...

    async def export_tasks(self, fmt: str = "json", show_all: bool = False) -> str:
        """导出任务数据，返回格式化字符串."""
        ...

    async def list_templates(self) -> list[tuple[str, str]]:
        """列出可用模板，返回 [(name, description), ...]."""
        ...

    async def list_plugins(self) -> list[dict[str, Any]]:
        """列出已注册插件，返回 [{name, version, description}, ...]."""
        ...


# ---------------------------------------------------------------------------
# LocalClient — 直连 FlowApp 的本地适配器
# ---------------------------------------------------------------------------

class LocalClient:
    """Daemon 未运行时的本地直连适配器.

    包装 FlowApp 的内部操作，将其映射为 FlowClient 契约的粗粒度 API。
    所有领域逻辑在此汇聚，CLI 层无需触碰 repo / engine。
    """

    def __init__(self) -> None:
        from flow_engine.app import FlowApp
        self._app = FlowApp()

    async def add_task(
        self,
        title: str,
        priority: int = 2,
        ddl: str | None = None,
        tags: list[str] | None = None,
        template_name: str | None = None,
    ) -> dict[str, Any]:
        app = self._app

        if template_name:
            tmpl = app.templates.get(template_name)
            if tmpl is None:
                raise ValueError(f"未找到模板: {template_name}")
            base_id = await app.repo.next_id()
            parsed_ddl = datetime.strptime(ddl, "%Y-%m-%d") if ddl else None
            output = tmpl.create(base_id=base_id, title=title, priority=priority, ddl=parsed_ddl)
            tasks = await app.repo.load_all()
            tasks.extend(output.tasks)
            await app.repo.save_all(tasks)
            if app.config.git.auto_commit:
                await asyncio.to_thread(
                    app.vcs.commit, f"{app.config.git.commit_prefix} add template:{template_name}"
                )
            return {
                "template": template_name,
                "tasks": [{"id": t.id, "title": t.title, "priority": t.priority} for t in output.tasks],
            }

        from flow_engine.storage.task_model import Task
        parsed_ddl = datetime.strptime(ddl, "%Y-%m-%d") if ddl else None
        task = Task(
            id=await app.repo.next_id(),
            title=title,
            priority=priority,
            ddl=parsed_ddl,
            tags=list(tags or []),
        )
        tasks = await app.repo.load_all()
        tasks.append(task)
        await app.repo.save_all(tasks)
        if app.config.git.auto_commit:
            await asyncio.to_thread(
                app.vcs.commit, f"{app.config.git.commit_prefix} add #{task.id} {task.title}"
            )
        return {"id": task.id, "title": task.title, "priority": task.priority}

    async def list_tasks(
        self,
        show_all: bool = False,
        filter_state: str | None = None,
        filter_tag: str | None = None,
        filter_priority: str | None = None,
    ) -> list[dict[str, Any]]:
        app = self._app
        tasks = await app.repo.load_all()

        from flow_engine.storage.filters import TaskFilter
        from flow_engine.state.machine import TaskState

        tf = TaskFilter(tasks)
        if not show_all:
            tf = tf.exclude_terminal()
        if filter_state:
            state = TaskState(filter_state.replace("_", " ").title())
            tf = tf.by_state(state)
        if filter_tag:
            tf = tf.by_tag(filter_tag)
        if filter_priority:
            if "-" in filter_priority:
                lo, hi = filter_priority.split("-", 1)
                tf = tf.by_priority(int(lo), int(hi))
            else:
                p = int(filter_priority)
                tf = tf.by_priority(p, p)

        filtered = tf.results()
        ranked = app.ranker.rank(filtered) if filtered else []

        return [
            {
                "id": t.id,
                "title": t.title,
                "state": t.state.value,
                "priority": t.priority,
                "ddl": t.ddl.strftime("%m-%d") if t.ddl else None,
                "score": round(score, 2) if isinstance(ranked[0], tuple) else None,
            }
            for i, t in enumerate(ranked if not isinstance(ranked[0], tuple) else [r[0] for r in ranked])
            for score in [ranked[i][1] if isinstance(ranked[0], tuple) else None]
        ] if ranked else []

    async def start_task(self, task_id: int) -> dict[str, Any]:
        app = self._app
        tasks = await app.repo.load_all()
        task = self._find(tasks, task_id)

        paused = await app.engine.ensure_single_active(tasks, task_id)
        for p in paused:
            if app.config.context.capture_on_switch:
                await asyncio.to_thread(app.context.capture, p.id)

        from flow_engine.state.machine import TaskState
        await app.engine.transition(task, TaskState.IN_PROGRESS)
        task.started_at = datetime.now()
        await app.repo.save_all(tasks)

        # 尝试恢复现场
        snapshot = await asyncio.to_thread(app.context.restore_latest, task_id)
        return {
            "id": task.id,
            "title": task.title,
            "paused": [p.id for p in paused],
            "restored_window": snapshot.active_window if snapshot and snapshot.active_window else None,
        }

    async def done_task(self) -> dict[str, Any]:
        app = self._app
        tasks = await app.repo.load_all()
        active = next((t for t in tasks if t.is_active), None)
        if not active:
            raise ValueError("当前没有进行中的任务")

        from flow_engine.state.machine import TaskState
        await app.engine.transition(active, TaskState.DONE)
        await app.repo.save_all(tasks)
        return {"id": active.id, "title": active.title}

    async def pause_task(self) -> dict[str, Any]:
        app = self._app
        tasks = await app.repo.load_all()
        active = next((t for t in tasks if t.is_active), None)
        if not active:
            raise ValueError("当前没有进行中的任务")

        if app.config.context.capture_on_switch:
            await asyncio.to_thread(app.context.capture, active.id)

        from flow_engine.state.machine import TaskState
        await app.engine.transition(active, TaskState.PAUSED)
        await app.repo.save_all(tasks)
        return {"id": active.id, "title": active.title}

    async def resume_task(self, task_id: int) -> dict[str, Any]:
        app = self._app
        tasks = await app.repo.load_all()
        task = self._find(tasks, task_id)

        from flow_engine.state.machine import TaskState
        if task.state == TaskState.BLOCKED:
            await app.engine.transition(task, TaskState.READY)
            task.block_reason = ""
        elif task.state == TaskState.PAUSED:
            await app.engine.ensure_single_active(tasks, task_id)
            await app.engine.transition(task, TaskState.IN_PROGRESS)
            task.started_at = datetime.now()
        else:
            raise ValueError(f"任务 #{task_id} 当前状态为 {task.state.value}，无法恢复")

        await app.repo.save_all(tasks)
        return {"id": task.id, "title": task.title, "state": task.state.value}

    async def block_task(self, task_id: int, reason: str = "") -> dict[str, Any]:
        app = self._app
        tasks = await app.repo.load_all()
        task = self._find(tasks, task_id)

        from flow_engine.state.machine import TaskState
        await app.engine.transition(task, TaskState.BLOCKED)
        task.block_reason = reason
        await app.repo.save_all(tasks)
        return {"id": task.id, "title": task.title, "reason": reason}

    async def get_status(self) -> dict[str, Any]:
        app = self._app
        active = await app.repo.get_active()
        if not active:
            return {"active": None}

        duration_min = None
        if active.started_at:
            delta = datetime.now() - active.started_at
            duration_min = int(delta.total_seconds() // 60)

        break_suggested = False
        if active.started_at:
            elapsed = (datetime.now() - active.started_at).total_seconds() / 60
            if elapsed >= app.config.focus.break_interval_minutes:
                break_suggested = True

        return {
            "active": {
                "id": active.id,
                "title": active.title,
                "priority": active.priority,
                "state": active.state.value,
                "duration_min": duration_min,
            },
            "break_suggested": break_suggested,
        }

    async def breakdown_task(self, task_id: int) -> list[str]:
        app = self._app
        task = self._find(await app.repo.load_all(), task_id)
        return app.breaker.breakdown(task)

    async def export_tasks(self, fmt: str = "json", show_all: bool = False) -> str:
        app = self._app
        exporter = app.exporters.get(fmt)
        if exporter is None:
            raise ValueError(f"未知导出格式: {fmt}")

        tasks = await app.repo.load_all()
        if not show_all:
            tasks = [t for t in tasks if not t.is_terminal]
        return exporter.export(tasks)

    async def list_templates(self) -> list[tuple[str, str]]:
        return self._app.templates.list_all()

    async def list_plugins(self) -> list[dict[str, Any]]:
        app = self._app
        result = []
        for name in app.plugins.names():
            plugin = app.plugins.get(name)
            if plugin:
                result.append({
                    "name": name,
                    "version": plugin.manifest.version,
                    "description": plugin.manifest.description,
                })
        return result

    # ── 内部工具 ──

    @staticmethod
    def _find(tasks: list, task_id: int):
        task = next((t for t in tasks if t.id == task_id), None)
        if task is None:
            raise ValueError(f"未找到任务 #{task_id}")
        return task


# ---------------------------------------------------------------------------
# RemoteClient — IPC 适配器（Daemon 运行时）
# ---------------------------------------------------------------------------

class RemoteClient:
    """Daemon 运行时的 IPC 远程适配器.

    将 FlowClient 契约的每个方法映射为对应的 IPC RPC call。
    只传输最小必要参数（task_id、title 等），不传整个任务列表。
    """

    def __init__(self) -> None:
        from flow_engine.ipc.client import IPCClient
        self._ipc = IPCClient()

    async def connect(self) -> None:
        await self._ipc.connect()

    async def close(self) -> None:
        await self._ipc.close()

    async def add_task(
        self,
        title: str,
        priority: int = 2,
        ddl: str | None = None,
        tags: list[str] | None = None,
        template_name: str | None = None,
    ) -> dict[str, Any]:
        return await self._ipc.call(
            "task.add",
            title=title,
            priority=priority,
            ddl=ddl,
            tags=tags or [],
            template_name=template_name,
        )

    async def list_tasks(
        self,
        show_all: bool = False,
        filter_state: str | None = None,
        filter_tag: str | None = None,
        filter_priority: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._ipc.call(
            "task.list",
            show_all=show_all,
            filter_state=filter_state,
            filter_tag=filter_tag,
            filter_priority=filter_priority,
        )

    async def start_task(self, task_id: int) -> dict[str, Any]:
        return await self._ipc.call("task.start", task_id=task_id)

    async def done_task(self) -> dict[str, Any]:
        return await self._ipc.call("task.done")

    async def pause_task(self) -> dict[str, Any]:
        return await self._ipc.call("task.pause")

    async def resume_task(self, task_id: int) -> dict[str, Any]:
        return await self._ipc.call("task.resume", task_id=task_id)

    async def block_task(self, task_id: int, reason: str = "") -> dict[str, Any]:
        return await self._ipc.call("task.block", task_id=task_id, reason=reason)

    async def get_status(self) -> dict[str, Any]:
        return await self._ipc.call("status")

    async def breakdown_task(self, task_id: int) -> list[str]:
        return await self._ipc.call("task.breakdown", task_id=task_id)

    async def export_tasks(self, fmt: str = "json", show_all: bool = False) -> str:
        return await self._ipc.call("task.export", fmt=fmt, show_all=show_all)

    async def list_templates(self) -> list[tuple[str, str]]:
        return await self._ipc.call("templates.list")

    async def list_plugins(self) -> list[dict[str, Any]]:
        return await self._ipc.call("plugins.list")


# ---------------------------------------------------------------------------
# 工厂函数 — 自动探测模式
# ---------------------------------------------------------------------------

async def create_client() -> FlowClient:
    """根据 Daemon 运行状态自动创建合适的 FlowClient.

    Daemon 运行中 → RemoteClient (IPC)
    Daemon 未运行 → LocalClient (直连)
    Daemon PID 存在但连接失败 → 静默降级为 LocalClient
    """
    from flow_engine.daemon import FlowDaemon

    if FlowDaemon.is_running():
        remote = RemoteClient()
        try:
            await remote.connect()
            return remote
        except ConnectionError:
            logger.warning("Daemon PID exists but connection failed, falling back to local mode")
            return LocalClient()
    return LocalClient()
