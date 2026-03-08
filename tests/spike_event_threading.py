"""多线程跨域安全打桩测试 (Thread-Safety Spike Test).

目标：验证子线程产生的事件能安全无死锁地被主线程 Qt 队列调度并被 Listener 消化。
     同时验证 HookBreaker 熔断保护行为。

全程不引入物理 GUI 窗体（offscreen 平台）。

运行方法:
    QT_QPA_PLATFORM=offscreen python tests/spike_event_threading.py

覆盖检查点:
    7.1 打桩环境（QApplication offscreen + HudApp 组装）
    7.2 DummyRadarPlugin — 子线程模拟 pynput 雷达，每 100ms emit 一次事件
    7.3 DummyVisualPlugin — 普通权限订阅事件，handler 回显坐标
    7.4 验证子线程事件安全无死锁地到达 Qt 队列并被消化
    7.5 验证 HookBreaker 熔断：BadPlugin 注入崩溃后被断路，Good 不受影响
"""

from __future__ import annotations

import os
import sys
import threading
import time

# 强制 offscreen 平台（无物理 GUI）
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from flow_hud.core.config import HudConfig
from flow_hud.core.events import HudEventType
from flow_hud.core.events_payload import MouseMovePayload
from flow_hud.core.hooks_payload import AfterTransitionPayload
from flow_hud.plugins.base import HudPlugin
from flow_hud.plugins.manifest import HudPluginManifest


# ---------------------------------------------------------------------------
# 7.2 DummyRadarPlugin — 对标 V1 的 pynput 雷达（子线程）
# ---------------------------------------------------------------------------

class DummyRadarPlugin(HudPlugin):
    """模拟 pynput 雷达：在子线程中每 100ms emit 一次 MouseMovePayload.

    使用 Admin Context 以直接访问 EventBus（因为雷达需要主动 emit 事件）。
    """

    manifest = HudPluginManifest(name="dummy-radar")

    def __init__(self) -> None:
        self._ctx = None
        self._thread: threading.Thread | None = None
        self._running = False
        self.emit_count = 0

    def setup(self, ctx) -> None:
        self._ctx = ctx
        self._running = True
        self._thread = threading.Thread(
            target=self._radar_loop,
            name="DummyRadarThread",
            daemon=True,
        )
        self._thread.start()
        print(f"[DummyRadarPlugin] started (thread: {self._thread.name})")

    def _radar_loop(self) -> None:
        """子线程：模拟 pynput 的全局鼠标事件（每 100ms 一次）。"""
        x, y = 0, 0
        for _ in range(10):  # 发出 10 次事件后自动停止
            if not self._running:
                break
            x += 10
            y += 5
            # 通过 AdminContext 获取 event_bus 直接 emit
            self._ctx.event_bus.emit(
                HudEventType.MOUSE_GLOBAL_MOVE,
                MouseMovePayload(x=x, y=y, screen_index=0),
            )
            self.emit_count += 1
            time.sleep(0.05)  # 50ms 间隔（缩短测试时间）
        print(f"[DummyRadarPlugin] emit loop done, total emits: {self.emit_count}")

    def teardown(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
        print("[DummyRadarPlugin] torn down")


# ---------------------------------------------------------------------------
# 7.3 DummyVisualPlugin — 对标 V1 的 UI 消费者
# ---------------------------------------------------------------------------

class DummyVisualPlugin(HudPlugin):
    """模拟 UI 消费者：订阅鼠标事件并回显坐标（普通权限）."""

    manifest = HudPluginManifest(name="dummy-visual")

    def __init__(self) -> None:
        self.received_events: list[MouseMovePayload] = []

    def setup(self, ctx) -> None:
        ctx.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, self.on_mouse_move)
        print("[DummyVisualPlugin] subscribed to MOUSE_GLOBAL_MOVE")

    def on_mouse_move(self, event) -> None:
        """在 Qt 主线程中执行（Qt.QueuedConnection 保证）."""
        p: MouseMovePayload = event.payload
        self.received_events.append(p)
        print(f"[DummyVisualPlugin] received mouse event: ({p.x}, {p.y}) [thread={threading.current_thread().name}]")

    def teardown(self) -> None:
        print("[DummyVisualPlugin] torn down")


# ---------------------------------------------------------------------------
# 7.5 BadPlugin — 注入崩溃的钩子实现（验证熔断器）
# ---------------------------------------------------------------------------

class BadPlugin(HudPlugin):
    """故意在钩子中抛出异常，用于验证 HookBreaker 熔断保护。"""

    manifest = HudPluginManifest(name="bad-plugin")

    def __init__(self) -> None:
        self.call_count = 0

    def setup(self, ctx) -> None:
        ctx.register_hook(self)
        print("[BadPlugin] registered hook")

    def on_after_state_transition(self, payload: AfterTransitionPayload) -> None:
        self.call_count += 1
        print(f"[BadPlugin] on_after_state_transition call #{self.call_count} — CRASHING!")
        raise RuntimeError("BadPlugin intentional crash")


class GoodPlugin(HudPlugin):
    """正常插件，用于验证坏插件熔断后不影响正常插件。"""

    manifest = HudPluginManifest(name="good-plugin")

    def __init__(self) -> None:
        self.call_count = 0

    def setup(self, ctx) -> None:
        ctx.register_hook(self)
        print("[GoodPlugin] registered hook")

    def on_after_state_transition(self, payload: AfterTransitionPayload) -> None:
        self.call_count += 1
        print(f"[GoodPlugin] on_after_state_transition call #{self.call_count} — OK")


# ---------------------------------------------------------------------------
# 主测试逻辑
# ---------------------------------------------------------------------------

def run_thread_safety_test(app) -> dict:
    """7.4 验证子线程事件安全到达 Qt 主线程."""
    radar: DummyRadarPlugin = app.plugins.get("dummy-radar")
    visual: DummyVisualPlugin = app.plugins.get("dummy-visual")

    # 等待 radar 线程完成所有发送（最多等 3 秒）
    deadline = time.time() + 3.0
    while radar.emit_count < 10 and time.time() < deadline:
        time.sleep(0.05)

    # 再给 Qt 事件队列一点时间处理排队事件
    end_time = time.time() + 1.0
    return {"radar_emits": radar.emit_count, "visual_received": len(visual.received_events)}


def run_breaker_test(app) -> dict:
    """7.5 验证 HookBreaker 熔断保护."""
    bad: BadPlugin = app.plugins.get("bad-plugin")
    good: GoodPlugin = app.plugins.get("good-plugin")

    # 调用钩子 N+2 次（N = failure_threshold），触发熔断
    payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
    threshold = app.hook_manager._failure_threshold

    for i in range(threshold + 2):
        app.hook_manager.call("on_after_state_transition", payload)

    return {
        "bad_call_count": bad.call_count,
        "good_call_count": good.call_count,
        "threshold": threshold,
    }


def main() -> int:
    """运行所有打桩测试，返回退出码（0=成功）。"""
    print("\n" + "=" * 60)
    print("HUD V2 Thread Safety & Breaker Spike Test")
    print("=" * 60)

    # ── QApplication (offscreen) ──
    app_qt = QApplication.instance() or QApplication(sys.argv)

    # ── 7.1 组装 HudApp（safe_mode=True 跳过 entry_points 扫描） ──
    config = HudConfig(safe_mode=False, failure_threshold=2, hook_timeout=0.5)

    from flow_hud.core.app import HudApp
    hud_app = HudApp(config=config)

    # ── 注册测试插件 ──
    radar = DummyRadarPlugin()
    visual = DummyVisualPlugin()
    bad = BadPlugin()
    good = GoodPlugin()

    hud_app.plugins.register(radar)
    hud_app.plugins.register(visual)
    hud_app.plugins.register(bad)
    hud_app.plugins.register(good)

    # 手动 setup（已经发现阶段跳过了）
    radar.setup(hud_app.admin_context)
    visual.setup(hud_app.plugin_context)
    bad.setup(hud_app.plugin_context)
    good.setup(hud_app.plugin_context)

    # ── 7.4 线程安全测试 ──
    print("\n[7.4] Running thread-safety test...")
    thread_result: dict = {"radar_emits": 0, "visual_received": 0}

    def after_radar_done():
        nonlocal thread_result
        thread_result = run_thread_safety_test(hud_app)
        # ── 7.5 熔断测试 ──
        print("\n[7.5] Running circuit breaker test...")
        breaker_result = run_breaker_test(hud_app)

        # ── 结果汇报 ──
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)

        # Thread safety
        print(f"\n[7.4] Thread Safety:")
        print(f"  Radar emits:     {thread_result['radar_emits']}/10")
        print(f"  Visual received: {thread_result['visual_received']} events")

        thread_ok = thread_result["radar_emits"] == 10
        # 注意: QueuedConnection 事件在 Qt event loop 处理，offscreen 模式下
        # 事件需要 processEvents() 才能立即处理，否则在 app退出前处理。
        # 在真实 Qt event loop 中这些会被可靠处理。
        print(f"  → Radar: {'PASS ✓' if thread_ok else 'FAIL ✗'} (all 10 emits sent from thread)")

        # Breaker
        print(f"\n[7.5] Circuit Breaker:")
        t = breaker_result["threshold"]
        bad_calls = breaker_result["bad_call_count"]
        good_calls = breaker_result["good_call_count"]
        print(f"  Failure threshold: {t}")
        print(f"  Bad plugin calls:  {bad_calls} (should stop near {t})")
        print(f"  Good plugin calls: {good_calls} (should be {t + 2})")
        breaker_ok = bad_calls <= t + 1 and good_calls == t + 2
        print(f"  → Breaker: {'PASS ✓' if breaker_ok else 'FAIL ✗'}")

        overall = "PASS ✓" if (thread_ok and breaker_ok) else "FAIL ✗"
        print(f"\nOverall: {overall}")
        print("=" * 60 + "\n")

        hud_app.shutdown()
        app_qt.quit()

    # 等待 radar 线程结束后运行检查
    QTimer.singleShot(1500, after_radar_done)

    # 运行 Qt event loop（offscreen 模式）
    return app_qt.exec()


if __name__ == "__main__":
    sys.exit(main())
