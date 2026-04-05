"""心流引擎 TUI — 基于 Textual 的沉浸式终端监控面板.

设计要点：
- 连接 Ghost Daemon 的 IPC 客户端，实时消费推送事件。
- 三区布局：顶部状态栏 + 中央任务列表 + 底部专注计时器。
- 完全异步：Textual 原生 asyncio 事件循环与 IPC 推送无缝融合。
- 与 Daemon 完全解耦：TUI 只是一个"纯展示客户端"，零业务逻辑。

架构：
    ┌─────────────────────────────────┐
    │         FlowTUI (Textual)       │
    │  ┌───────────────────────────┐  │
    │  │  StatusBar (连接状态)      │  │
    │  ├───────────────────────────┤  │
    │  │  TaskTable (任务列表)      │  │
    │  │  · #1 [P1] 写论文 ★ 进行中  │  │
    │  │  · #2 [P2] 买咖啡   就绪   │  │
    │  ├───────────────────────────┤  │
    │  │  TimerDisplay (专注计时)   │  │
    │  │  ⏱ 00:23:45               │  │
    │  └───────────────────────────┘  │
    └─────────────────────────────────┘
              │ IPC Client
              ▼
    ┌─────────────────────────────────┐
    │        Ghost Daemon             │
    └─────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static

from flow_engine.ipc.client import IPCClient
from flow_engine.ipc.protocol import Push

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 自定义组件
# ---------------------------------------------------------------------------

class ConnectionStatus(Static):
    """Daemon 连接状态指示器."""

    connected = reactive(False)

    def render(self) -> str:
        if self.connected:
            return "🟢 已连接 Ghost Daemon"
        return "🔴 未连接 — 请先运行 flow daemon start"


class TimerDisplay(Static):
    """专注计时器显示 — 响应 Daemon 的 timer.tick 推送."""

    elapsed = reactive(0)
    task_title = reactive("")

    def render(self) -> str:
        if not self.task_title:
            return "⏸️  无活跃任务"
        td = timedelta(seconds=self.elapsed)
        hours, remainder = divmod(int(td.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"⏱  {hours:02d}:{minutes:02d}:{seconds:02d}  │  {self.task_title}"


# ---------------------------------------------------------------------------
# 主应用
# ---------------------------------------------------------------------------

class FlowTUI(App):
    """心流引擎终端监控面板."""

    TITLE = "Flow Engine — 心流监控"
    CSS = """
    Screen {
        layout: vertical;
    }
    #status-bar {
        height: 1;
        background: $surface;
        color: $text;
        padding: 0 1;
    }
    #timer-bar {
        height: 1;
        background: $primary;
        color: $text;
        padding: 0 1;
    }
    #task-table {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("q", "quit", "退出"),
        ("r", "refresh", "刷新"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._client = IPCClient()
        self._listen_task: asyncio.Task | None = None

    def compose(self) -> ComposeResult:
        """构建 TUI 布局."""
        yield Header()
        yield ConnectionStatus(id="status-bar")
        yield DataTable(id="task-table")
        yield TimerDisplay(id="timer-bar")
        yield Footer()

    async def on_mount(self) -> None:
        """应用启动后：连接 Daemon + 加载初始数据 + 开始监听推送."""
        # 初始化任务列表表头
        table = self.query_one(DataTable)
        table.add_columns("ID", "优先级", "标题", "状态", "引力分")

        # 尝试连接 Daemon
        await self._connect_daemon()

    async def _connect_daemon(self) -> None:
        """连接 Ghost Daemon 并启动推送监听."""
        status = self.query_one(ConnectionStatus)
        try:
            await self._client.connect()
            status.connected = True
            # 加载初始任务列表
            await self._refresh_tasks()
            # 启动后台推送监听
            self._listen_task = asyncio.create_task(self._listen_loop())
        except ConnectionError:
            status.connected = False

    async def _refresh_tasks(self) -> None:
        """从 Daemon 拉取最新任务列表."""
        try:
            result = await self._client.call("task.list")
            table = self.query_one(DataTable)
            table.clear()
            if isinstance(result, list):
                for t in result:
                    table.add_row(
                        str(t.get("id", "?")),
                        f"P{t.get('priority', '?')}",
                        str(t.get("title", "")),
                        str(t.get("state", "")),
                        str(t.get("score", "")),
                    )
        except Exception as exc:
            logger.warning("failed to refresh tasks: %s", exc)

    async def _listen_loop(self) -> None:
        """持续监听 Daemon 推送 — 更新 TUI 状态."""
        try:
            async for push in self._client.listen_pushes():
                await self._handle_push(push)
        except Exception:
            logger.exception("push listen loop error")
            status = self.query_one(ConnectionStatus)
            status.connected = False

    async def _handle_push(self, push: Push) -> None:
        """处理 Daemon 推送事件."""
        if push.event == "task.state_changed":
            await self._refresh_tasks()
        elif push.event == "timer.tick":
            timer = self.query_one(TimerDisplay)
            timer.elapsed = push.data.get("elapsed", timer.elapsed + 1)
            timer.task_title = push.data.get("title", timer.task_title)

    async def action_refresh(self) -> None:
        """手动刷新任务列表."""
        await self._refresh_tasks()

    async def on_unmount(self) -> None:
        """退出时清理连接."""
        if self._listen_task:
            self._listen_task.cancel()
        await self._client.close()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def run_tui() -> None:
    """启动 TUI 监控面板."""
    app = FlowTUI()
    app.run()


if __name__ == "__main__":
    run_tui()
