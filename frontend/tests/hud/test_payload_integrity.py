"""Tests for Payload Integrity — 验证载荷完整性与安全性加固.

验证:
- 事件载荷必须是 frozen dataclass
- Hook 载荷根据策略区分 frozen/mutable
- EventBus.emit() 拦截非 dataclass 或非 frozen 载荷
- HookManager.call() 拦截不符合策略要求的载荷
"""

import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from dataclasses import dataclass
from flow_hud.core.events import HudEventBus, HudEventType
from flow_hud.core.hooks import HudHookManager, HudHookStrategy
from flow_hud.core.events_payload import MouseMovePayload
from flow_hud.core.hooks_payload import BeforeTransitionPayload, VetoTransitionPayload

@dataclass
class NotFrozenPayload:
    x: int

@dataclass(frozen=True)
class FrozenPayload:
    x: int

class TestPayloadIntegrity:
    def test_event_bus_rejects_non_dataclass(self):
        bus = HudEventBus()
        with pytest.raises(TypeError, match="must be a dataclass"):
            bus.emit(HudEventType.MOUSE_GLOBAL_MOVE, {"x": 1})

    def test_event_bus_rejects_not_frozen_dataclass(self):
        bus = HudEventBus()
        with pytest.raises(TypeError, match="must be frozen"):
            bus.emit(HudEventType.MOUSE_GLOBAL_MOVE, NotFrozenPayload(x=1))

    def test_event_bus_accepts_frozen_dataclass(self):
        bus = HudEventBus()
        # Should not raise
        bus.emit(HudEventType.MOUSE_GLOBAL_MOVE, MouseMovePayload(x=1, y=2))

    def test_hook_manager_rejects_non_dataclass(self):
        mgr = HudHookManager()
        with pytest.raises(TypeError, match="must be a dataclass"):
            mgr.call("on_after_state_transition", {"old": "ghost"})

    def test_hook_manager_enforces_frozen_for_parallel(self):
        mgr = HudHookManager()
        # on_after_state_transition is PARALLEL
        with pytest.raises(TypeError, match="requires a frozen payload"):
            mgr.call("on_after_state_transition", NotFrozenPayload(x=1))

    def test_hook_manager_accepts_frozen_for_parallel(self):
        mgr = HudHookManager()
        # Should not raise
        mgr.call("on_after_state_transition", FrozenPayload(x=1))

    def test_hook_manager_enforces_mutable_for_waterfall(self):
        mgr = HudHookManager()
        # before_widget_register is WATERFALL
        with pytest.raises(TypeError, match="requires a mutable payload"):
            mgr.call("before_widget_register", FrozenPayload(x=1))

    def test_hook_manager_accepts_mutable_for_waterfall(self):
        mgr = HudHookManager()
        # Should not raise
        mgr.call("before_widget_register", NotFrozenPayload(x=1))
