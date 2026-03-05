"""Daemon 生命周期管理 — Ghost Daemon 的启动/停止/状态控制.

设计要点：
- FlowApp 的全部核心状态在 Daemon 中长期存活（计时器、事件总线、存储层）。
- IPC Server 将 FlowApp 的能力暴露为远程方法调用。
- PID 文件用于进程管理和防止重复启动。
- 与 app.py 完全解耦：只通过注入的 FlowApp 实例操作。

架构：
    ┌──────────────────────────────────┐
    │          FlowDaemon              │
    │  ┌──────────┐  ┌──────────────┐  │
    │  │ FlowApp  │  │  IPC Server  │  │
    │  │ (core)   │  │  (transport) │  │
    │  └──────────┘  └──────────────┘  │
    │         │              │         │
    │    EventBus ──── broadcast() ──► │ → TUI/CLI
    └──────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from flow_engine.app import FlowApp
from flow_engine.events import EventType
from flow_engine.ipc.protocol import Push
from flow_engine.ipc.server import IPCServer
from flow_engine.state.machine import TaskState

logger = logging.getLogger(__name__)

# PID 文件路径
DEFAULT_PID_PATH = Path.home() / ".flow_engine" / "daemon.pid"


class FlowDaemon:
    """心流引擎常驻守护进程.

    职责：
    1. 持有 FlowApp 的完整生命周期
    2. 暴露 IPC 方法供 CLI/TUI 远程调用
    3. 将事件总线的变更广播给所有连接的客户端
    4. 管理 PID 文件防止重复启动
    """

    def __init__(self, app: FlowApp | None = None) -> None:
        self._app = app or FlowApp()
        self._ipc = IPCServer()
        self._pid_path = DEFAULT_PID_PATH
        self._running = False

        # 注册 IPC 方法
        self._register_methods()
        # 连接事件总线 → IPC 广播
        self._wire_broadcasts()

    # ── 生命周期 ──

    async def start(self) -> None:
        """启动 Daemon — IPC 服务 + 事件循环."""
        self._write_pid()
        self._install_signal_handlers()
        self._running = True

        await self._ipc.start()
        logger.info("FlowDaemon started (PID %d)", os.getpid())

        # 保持运行直到收到停止信号
        try:
            while self._running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            await self.stop()

    async def stop(self) -> None:
        """优雅关闭 Daemon."""
        self._running = False
        await self._ipc.stop()
        await self._app.shutdown()
        self._remove_pid()
        logger.info("FlowDaemon stopped")

    # ── PID 管理 ──

    def _write_pid(self) -> None:
        """写入 PID 文件."""
        self._pid_path.parent.mkdir(parents=True, exist_ok=True)
        self._pid_path.write_text(str(os.getpid()))

    def _remove_pid(self) -> None:
        """清理 PID 文件."""
        if self._pid_path.exists():
            self._pid_path.unlink()

    @classmethod
    def is_running(cls) -> bool:
        """检查 Daemon 是否在运行."""
        pid_path = DEFAULT_PID_PATH
        if not pid_path.exists():
            return False
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)  # 不发信号，仅检查进程存在
            return True
        except (ProcessLookupError, ValueError):
            # PID 文件残留但进程不存在
            pid_path.unlink(missing_ok=True)
            return False

    @classmethod
    def stop_running(cls) -> bool:
        """向运行中的 Daemon 发送 SIGTERM."""
        pid_path = DEFAULT_PID_PATH
        if not pid_path.exists():
            return False
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            return True
        except (ProcessLookupError, ValueError):
            pid_path.unlink(missing_ok=True)
            return False

    # ── 信号处理 ──

    def _install_signal_handlers(self) -> None:
        """注册 SIGTERM/SIGINT 信号处理."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._on_signal, sig)

    def _on_signal(self, sig: signal.Signals) -> None:
        """收到终止信号时优雅关闭."""
        logger.info("received signal %s, shutting down...", sig.name)
        self._running = False

    # ── IPC 方法注册 ──

    def _register_methods(self) -> None:
        """将 FlowApp 的核心能力映射为 IPC 远程方法."""
        self._ipc.register("task.list", self._handle_task_list)
        self._ipc.register("task.add", self._handle_task_add)
        self._ipc.register("task.start", self._handle_task_start)
        self._ipc.register("task.done", self._handle_task_done)
        self._ipc.register("task.pause", self._handle_task_pause)
        self._ipc.register("task.resume", self._handle_task_resume)
        self._ipc.register("task.block", self._handle_task_block)
        self._ipc.register("task.breakdown", self._handle_task_breakdown)
        self._ipc.register("task.export", self._handle_task_export)
        self._ipc.register("templates.list", self._handle_templates_list)
        self._ipc.register("plugins.list", self._handle_plugins_list)
        self._ipc.register("status", self._handle_status)
        self._ipc.register("ping", self._handle_ping)

    # ── IPC 方法实现 ──

    async def _handle_ping(self, params: dict[str, Any]) -> str:
        return "pong"

    async def _handle_status(self, params: dict[str, Any]) -> dict[str, Any]:
        """查询当前活跃任务与专注时长."""
        tasks = await self._app.repo.load_all()
        active = [t for t in tasks if t.state == TaskState.IN_PROGRESS]
        if not active:
            return {"active": None, "total_tasks": len(tasks)}

        task = active[0]
        return {
            "active": {
                "id": task.id,
                "title": task.title,
                "state": task.state.value,
                "priority": task.priority,
            },
            "total_tasks": len(tasks),
        }

    async def _handle_task_list(self, params: dict[str, Any]) -> list[dict]:
        """列出任务（支持过滤）."""
        tasks = await self._app.repo.load_all()
        show_all = params.get("show_all", False)

        from flow_engine.storage.filters import TaskFilter
        tf = TaskFilter(tasks)
        if not show_all:
            tf = tf.exclude_terminal()
        if fs := params.get("filter_state"):
            state = TaskState(fs.replace("_", " ").title())
            tf = tf.by_state(state)
        if ft := params.get("filter_tag"):
            tf = tf.by_tag(ft)
        if fp := params.get("filter_priority"):
            if "-" in fp:
                lo, hi = fp.split("-", 1)
                tf = tf.by_priority(int(lo), int(hi))
            else:
                p = int(fp)
                tf = tf.by_priority(p, p)

        filtered = tf.results()
        ranked = self._app.ranker.rank(filtered) if filtered else []

        result = []
        for item in ranked:
            if isinstance(item, tuple):
                t, score = item
            else:
                t, score = item, None
            result.append({
                "id": t.id,
                "title": t.title,
                "state": t.state.value,
                "priority": t.priority,
                "ddl": t.ddl.strftime("%m-%d") if t.ddl else None,
                "score": round(score, 2) if score is not None else None,
            })
        return result

    async def _handle_task_add(self, params: dict[str, Any]) -> dict[str, Any]:
        """添加新任务（支持 ddl/tags/template）."""
        from datetime import datetime
        from flow_engine.storage.task_model import Task

        # 模板模式
        template_name = params.get("template_name")
        if template_name:
            tmpl = self._app.templates.get(template_name)
            if tmpl is None:
                raise ValueError(f"未找到模板: {template_name}")
            base_id = await self._app.repo.next_id()
            ddl_str = params.get("ddl")
            parsed_ddl = datetime.strptime(ddl_str, "%Y-%m-%d") if ddl_str else None
            output = tmpl.create(
                base_id=base_id,
                title=params.get("title", ""),
                priority=params.get("priority", 2),
                ddl=parsed_ddl,
            )
            tasks = await self._app.repo.load_all()
            tasks.extend(output.tasks)
            await self._app.repo.save_all(tasks)
            return {
                "template": template_name,
                "tasks": [{"id": t.id, "title": t.title, "priority": t.priority} for t in output.tasks],
            }

        # 普通添加
        tasks = await self._app.repo.load_all()
        new_id = max((t.id for t in tasks), default=0) + 1
        ddl_str = params.get("ddl")
        task = Task(
            id=new_id,
            title=params["title"],
            priority=params.get("priority", 2),
            ddl=datetime.strptime(ddl_str, "%Y-%m-%d") if ddl_str else None,
            tags=params.get("tags", []),
        )
        tasks.append(task)
        await self._app.repo.save_all(tasks)
        await self._app.bus.emit(EventType.TASK_CREATED, {"task_id": task.id})
        return {"id": task.id, "title": task.title, "priority": task.priority}

    async def _handle_task_start(self, params: dict[str, Any]) -> dict[str, Any]:
        """开始执行任务."""
        from datetime import datetime
        task_id = params["task_id"]
        tasks = await self._app.repo.load_all()
        task = next((t for t in tasks if t.id == task_id), None)
        if not task:
            raise ValueError(f"task #{task_id} not found")

        paused = await self._app.engine.ensure_single_active(tasks, task_id)
        await self._app.engine.transition(task, TaskState.IN_PROGRESS)
        task.started_at = datetime.now()
        await self._app.repo.save_all(tasks)
        return {
            "id": task.id,
            "title": task.title,
            "paused": [t.id for t in paused],
        }

    async def _handle_task_done(self, params: dict[str, Any]) -> dict[str, Any]:
        """完成当前活跃任务（自动检测）."""
        tasks = await self._app.repo.load_all()
        active = next((t for t in tasks if t.state == TaskState.IN_PROGRESS), None)
        if not active:
            raise ValueError("当前没有进行中的任务")

        await self._app.engine.transition(active, TaskState.DONE)
        await self._app.repo.save_all(tasks)
        return {"id": active.id, "title": active.title}

    async def _handle_task_pause(self, params: dict[str, Any]) -> dict[str, Any]:
        """暂停当前活跃任务（自动检测）."""
        tasks = await self._app.repo.load_all()
        active = next((t for t in tasks if t.state == TaskState.IN_PROGRESS), None)
        if not active:
            raise ValueError("当前没有进行中的任务")

        await self._app.engine.transition(active, TaskState.PAUSED)
        await self._app.repo.save_all(tasks)
        return {"id": active.id, "title": active.title}

    async def _handle_task_resume(self, params: dict[str, Any]) -> dict[str, Any]:
        """恢复任务."""
        task_id = params["task_id"]
        tasks = await self._app.repo.load_all()
        task = next((t for t in tasks if t.id == task_id), None)
        if not task:
            raise ValueError(f"task #{task_id} not found")

        if task.state == TaskState.BLOCKED:
            await self._app.engine.transition(task, TaskState.READY)
            task.block_reason = ""
        elif task.state == TaskState.PAUSED:
            paused = await self._app.engine.ensure_single_active(tasks, task_id)
            await self._app.engine.transition(task, TaskState.IN_PROGRESS)
        else:
            raise ValueError(f"task #{task_id} is {task.state.value}, cannot resume")

        await self._app.repo.save_all(tasks)
        return {"id": task.id, "title": task.title, "state": task.state.value}

    async def _handle_task_block(self, params: dict[str, Any]) -> dict[str, Any]:
        """阻塞任务."""
        task_id = params["task_id"]
        reason = params.get("reason", "")
        tasks = await self._app.repo.load_all()
        task = next((t for t in tasks if t.id == task_id), None)
        if not task:
            raise ValueError(f"task #{task_id} not found")

        await self._app.engine.transition(task, TaskState.BLOCKED)
        task.block_reason = reason
        await self._app.repo.save_all(tasks)
        return {"id": task.id, "title": task.title, "reason": reason}

    async def _handle_task_breakdown(self, params: dict[str, Any]) -> list[str]:
        """AI 拆解任务."""
        task_id = params["task_id"]
        tasks = await self._app.repo.load_all()
        task = next((t for t in tasks if t.id == task_id), None)
        if not task:
            raise ValueError(f"task #{task_id} not found")
        return self._app.breaker.breakdown(task)

    async def _handle_task_export(self, params: dict[str, Any]) -> str:
        """导出任务数据."""
        fmt = params.get("fmt", "json")
        show_all = params.get("show_all", False)
        exporter = self._app.exporters.get(fmt)
        if exporter is None:
            raise ValueError(f"未知导出格式: {fmt}")
        tasks = await self._app.repo.load_all()
        if not show_all:
            tasks = [t for t in tasks if not t.is_terminal]
        return exporter.export(tasks)

    async def _handle_templates_list(self, params: dict[str, Any]) -> list[tuple[str, str]]:
        """列出可用模板."""
        return self._app.templates.list_all()

    async def _handle_plugins_list(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        """列出已注册插件."""
        result = []
        for name in self._app.plugins.names():
            plugin = self._app.plugins.get(name)
            if plugin:
                result.append({
                    "name": name,
                    "version": plugin.manifest.version,
                    "description": plugin.manifest.description,
                })
        return result

    # ── 事件总线 → IPC 广播 ──

    def _wire_broadcasts(self) -> None:
        """将关键事件总线事件桥接到 IPC 广播."""
        async def _on_state_changed(event: Any) -> None:
            await self._ipc.broadcast(Push(
                event="task.state_changed",
                data=event.data if hasattr(event, "data") else {},
            ))

        self._app.bus.subscribe(EventType.TASK_STATE_CHANGED, _on_state_changed)

    # ── 专注计时器广播 (Phase 3 核心) ──

    async def start_focus_timer(self, task_id: int) -> None:
        """启动专注计时器 — 每秒向所有 TUI 客户端广播 tick.

        此方法由 task.start 的 IPC handler 自动触发。
        """
        while self._running:
            await self._ipc.broadcast(Push(
                event="timer.tick",
                data={"task_id": task_id, "type": "focus"},
            ))
            await asyncio.sleep(1)


# ---------------------------------------------------------------------------
# 入口点
# ---------------------------------------------------------------------------

async def run_daemon() -> None:
    """Daemon 主入口 — 被 `flow daemon start` 调用."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    daemon = FlowDaemon()
    await daemon.start()
