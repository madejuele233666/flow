from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from flow_hud.core.events import HudEventType
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest

from .controller import TaskStatusController
from .models import TaskStatusSnapshot, TaskStatusUpdatedPayload
from .widget import TaskStatusWidget

if TYPE_CHECKING:
    from flow_hud.plugins.context import HudPluginContext


class TaskStatusPlugin(HudPlugin):
    manifest = HudPluginManifest(
        name="task-status",
        version="0.1.0",
        description="Task-status MVP widget for the Windows HUD",
        author="flow-hud",
        requires=["ipc-client"],
    )

    def __init__(self) -> None:
        self._ctx: HudPluginContext | None = None
        self._controller: TaskStatusController | None = None
        self._widget: TaskStatusWidget | None = None

    def setup(self, ctx: HudPluginContext) -> None:
        self._ctx = ctx
        self._widget = TaskStatusWidget()
        ctx.register_widget("task-status", self._widget)

        self._controller = TaskStatusController(
            request_status=lambda: asyncio.run(ctx.request_ipc("status")),
            publish_snapshot=self._publish_snapshot,
        )

        ctx.subscribe_event(HudEventType.IPC_MESSAGE_RECEIVED, self._on_ipc_message)
        ctx.subscribe_event(HudEventType.IPC_CONNECTION_ESTABLISHED, self._on_ipc_connection_established)
        ctx.subscribe_event(HudEventType.IPC_CONNECTION_LOST, self._on_ipc_connection_lost)
        ctx.subscribe_event(HudEventType.TASK_STATUS_UPDATED, self._on_task_status_updated)
        self._controller.bootstrap()

    def teardown(self) -> None:
        if self._widget is not None:
            self._widget.deleteLater()
        self._ctx = None
        self._controller = None
        self._widget = None

    def _publish_snapshot(self, snapshot: TaskStatusSnapshot) -> None:
        ctx = self._ctx
        if ctx is None:
            return
        ctx.event_bus.emit(
            HudEventType.TASK_STATUS_UPDATED,
            TaskStatusUpdatedPayload(snapshot=snapshot),
        )

    def _on_ipc_message(self, event) -> None:
        controller = self._controller
        if controller is None:
            return
        controller.handle_ipc_payload(event.payload)

    def _on_task_status_updated(self, event) -> None:
        widget = self._widget
        payload = event.payload
        if widget is None or payload is None:
            return
        widget.render_snapshot(payload.snapshot)

    def _on_ipc_connection_established(self, event) -> None:
        controller = self._controller
        payload = event.payload
        if controller is None or payload is None or getattr(payload, "connected", False) is not True:
            return
        controller.handle_connection_established()

    def _on_ipc_connection_lost(self, event) -> None:
        controller = self._controller
        payload = event.payload
        if controller is None or payload is None or getattr(payload, "connected", True) is not False:
            return
        controller.handle_connection_lost()
