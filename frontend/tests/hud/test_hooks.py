"""Tests for HudHookManager and HookBreaker.

Tests cover:
- 5 hook strategies: PARALLEL, WATERFALL, BAIL, BAIL_VETO, COLLECT
- HookBreaker circuit breaker: CLOSED/OPEN/HALF_OPEN 三态
- safe_mode / dev_mode flags
- register / unregister
- Unknown hook graceful handling

Note: HudEventBus tests require a QApplication (Qt event loop) and are in
test_events_qt.py for headless-safe separation.
"""

import time
import threading
import pytest

from flow_hud.core.hooks import (
    HudHookManager,
    HudHookSpec,
    HudHookStrategy,
    HUD_HOOK_SPECS,
    HookBreaker,
    _BreakerState,
)
from flow_hud.core.hooks_payload import (
    BeforeTransitionPayload,
    VetoTransitionPayload,
    AfterTransitionPayload,
    BeforeWidgetRegisterPayload,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_manager(**kwargs) -> HudHookManager:
    defaults = dict(hook_timeout=1.0, failure_threshold=3, recovery_timeout=60.0)
    defaults.update(kwargs)
    return HudHookManager(**defaults)


# ---------------------------------------------------------------------------
# HUD_HOOK_SPECS 注册表测试
# ---------------------------------------------------------------------------

class TestHudHookSpecs:
    def test_all_expected_hooks_present(self):
        assert "before_state_transition" in HUD_HOOK_SPECS
        assert "on_after_state_transition" in HUD_HOOK_SPECS
        assert "before_widget_register" in HUD_HOOK_SPECS

    def test_strategies_are_correct(self):
        assert HUD_HOOK_SPECS["before_state_transition"].strategy == HudHookStrategy.BAIL_VETO
        assert HUD_HOOK_SPECS["on_after_state_transition"].strategy == HudHookStrategy.PARALLEL
        assert HUD_HOOK_SPECS["before_widget_register"].strategy == HudHookStrategy.WATERFALL


# ---------------------------------------------------------------------------
# HookBreaker 测试
# ---------------------------------------------------------------------------

class TestHookBreaker:
    def test_initial_state_is_closed(self):
        b = HookBreaker(failure_threshold=3, recovery_timeout=60.0)
        assert b.state == _BreakerState.CLOSED
        assert not b.is_open

    def test_opens_after_threshold_failures(self):
        b = HookBreaker(failure_threshold=3, recovery_timeout=60.0)
        b.record_failure()
        b.record_failure()
        assert b.state == _BreakerState.CLOSED  # 还未到阈值
        b.record_failure()
        assert b.state == _BreakerState.OPEN
        assert b.is_open

    def test_success_resets_to_closed(self):
        b = HookBreaker(failure_threshold=3, recovery_timeout=60.0)
        b.record_failure()
        b.record_failure()
        b.record_success()
        assert b.state == _BreakerState.CLOSED
        assert b._failure_count == 0

    def test_transitions_to_half_open_after_timeout(self):
        b = HookBreaker(failure_threshold=1, recovery_timeout=0.05)  # 50ms 恢复窗口
        b.record_failure()
        assert b.state == _BreakerState.OPEN
        time.sleep(0.1)
        assert b.state == _BreakerState.HALF_OPEN
        assert not b.is_open


# ---------------------------------------------------------------------------
# HudHookManager — register / unregister
# ---------------------------------------------------------------------------

class TestHudHookManagerRegistration:
    def test_register_plugin_with_hook_methods(self):
        mgr = make_manager()

        class MyPlugin:
            name = "test-plugin"
            def before_state_transition(self, payload): pass
            def on_after_state_transition(self, payload): pass

        registered = mgr.register(MyPlugin())
        assert "before_state_transition" in registered
        assert "on_after_state_transition" in registered
        assert "before_widget_register" not in registered

    def test_register_plugin_with_no_hooks(self):
        mgr = make_manager()

        class NoHooksPlugin:
            name = "empty-plugin"

        registered = mgr.register(NoHooksPlugin())
        assert registered == []

    def test_unregister_removes_handler(self):
        mgr = make_manager()

        results = []

        class MyPlugin:
            name = "my-plugin"
            def on_after_state_transition(self, payload):
                results.append("called")

        p = MyPlugin()
        mgr.register(p)
        mgr.unregister(p)

        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
        mgr.call("on_after_state_transition", payload)
        assert results == []
        assert mgr._breakers == {}

    def test_register_is_idempotent_for_same_implementor(self):
        mgr = make_manager()
        calls = []

        class MyPlugin:
            name = "my-plugin"

            def on_after_state_transition(self, payload):
                calls.append("called")

        plugin = MyPlugin()
        mgr.register(plugin)
        mgr.register(plugin)

        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
        mgr.call("on_after_state_transition", payload)
        assert calls == ["called"]

        mgr.unregister(plugin)
        mgr.call("on_after_state_transition", payload)
        assert calls == ["called"]


# ---------------------------------------------------------------------------
# PARALLEL 策略测试
# ---------------------------------------------------------------------------

class TestParallelStrategy:
    def test_all_handlers_called(self):
        mgr = make_manager()
        calls = []

        class PA:
            name = "pa"
            def on_after_state_transition(self, p): calls.append("A")

        class PB:
            name = "pb"
            def on_after_state_transition(self, p): calls.append("B")

        mgr.register(PA())
        mgr.register(PB())

        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
        result = mgr.call("on_after_state_transition", payload)

        assert result is None  # PARALLEL 返回 None
        assert set(calls) == {"A", "B"}

    def test_one_failing_handler_does_not_stop_others(self):
        mgr = make_manager()
        calls = []

        class Failer:
            name = "failer"
            def on_after_state_transition(self, p): raise RuntimeError("boom")

        class Good:
            name = "good"
            def on_after_state_transition(self, p): calls.append("good")

        mgr.register(Failer())
        mgr.register(Good())

        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
        mgr.call("on_after_state_transition", payload)
        assert "good" in calls


# ---------------------------------------------------------------------------
# WATERFALL 策略测试
# ---------------------------------------------------------------------------

class TestWaterfallStrategy:
    def test_payload_can_be_mutated_by_plugin(self):
        mgr = make_manager()

        class Modifier:
            name = "modifier"
            def before_widget_register(self, p: BeforeWidgetRegisterPayload):
                p.slot = "top_right"  # 重定向插槽

        mgr.register(Modifier())

        payload = BeforeWidgetRegisterPayload(name="test-widget", slot="center")
        result = mgr.call("before_widget_register", payload)

        # WATERFALL 返回同一个 payload 对象（已被修改）
        assert result is payload
        assert result.slot == "top_right"

    def test_multiple_modifiers_chain(self):
        mgr = make_manager()

        class A:
            name = "a"
            def before_widget_register(self, p):
                p.slot = "bottom"

        class B:
            name = "b"
            def before_widget_register(self, p):
                p.slot = p.slot + "_left"

        mgr.register(A())
        mgr.register(B())

        payload = BeforeWidgetRegisterPayload(name="w", slot="center")
        result = mgr.call("before_widget_register", payload)
        assert result.slot == "bottom_left"


# ---------------------------------------------------------------------------
# BAIL_VETO 策略测试
# ---------------------------------------------------------------------------

class TestBailVetoStrategy:
    def test_all_agree_returns_true(self):
        mgr = make_manager()

        class Agree:
            name = "agree"
            def before_state_transition(self, p): return True

        mgr.register(Agree())

        payload = VetoTransitionPayload(current_state="ghost", target_state="pulse")
        result = mgr.call("before_state_transition", payload)
        assert result is True

    def test_one_veto_returns_false(self):
        mgr = make_manager()

        class Agree:
            name = "agree"
            def before_state_transition(self, p): return True

        class Vetoer:
            name = "vetoer"
            def before_state_transition(self, p): return False  # 一票否决

        mgr.register(Agree())
        mgr.register(Vetoer())

        payload = VetoTransitionPayload(current_state="ghost", target_state="pulse")
        result = mgr.call("before_state_transition", payload)
        assert result is False

    def test_no_handlers_returns_none(self):
        mgr = make_manager()
        payload = VetoTransitionPayload(current_state="ghost", target_state="pulse")
        result = mgr.call("before_state_transition", payload)
        assert result is None

    def test_none_return_treated_as_abstain(self):
        """返回 None 的 handler 视为弃权（不否决）。"""
        mgr = make_manager()

        class Abstain:
            name = "abstain"
            def before_state_transition(self, p): return None  # 弃权

        mgr.register(Abstain())

        payload = VetoTransitionPayload(current_state="ghost", target_state="pulse")
        result = mgr.call("before_state_transition", payload)
        assert result is True  # 无人否决 → 通过


# ---------------------------------------------------------------------------
# safe_mode 测试
# ---------------------------------------------------------------------------

class TestSafeMode:
    def test_safe_mode_skips_all_hooks(self):
        mgr = make_manager(safe_mode=True)
        calls = []

        class MyPlugin:
            name = "my"
            def on_after_state_transition(self, p): calls.append("called")

        mgr.register(MyPlugin())
        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
        mgr.call("on_after_state_transition", payload)
        assert calls == []


# ---------------------------------------------------------------------------
# HookBreaker 熔断保护测试（通过 HoodHookManager）
# ---------------------------------------------------------------------------

class TestHookBreakerIntegration:
    def test_breaker_opens_after_repeated_failures(self):
        """经过 N 次失败后 handler 被断路，不再调用。"""
        mgr = make_manager(failure_threshold=2, recovery_timeout=60.0, hook_timeout=0.5)
        call_count = [0]

        class BadPlugin:
            name = "bad"
            def on_after_state_transition(self, p):
                call_count[0] += 1
                raise RuntimeError("crash!")

        mgr.register(BadPlugin())
        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")

        # 调用 2 次 → 触发熔断
        mgr.call("on_after_state_transition", payload)
        mgr.call("on_after_state_transition", payload)
        count_after_open = call_count[0]

        # 再调用 1 次 → 应被断路（不再执行 handler）
        mgr.call("on_after_state_transition", payload)
        assert call_count[0] == count_after_open  # 没有增加

    def test_good_plugin_unaffected_by_bad_plugin_breaker(self):
        """坏插件熔断后，好插件不受影响。"""
        mgr = make_manager(failure_threshold=2, recovery_timeout=60.0, hook_timeout=0.5)
        good_calls = []

        class BadPlugin:
            name = "bad"
            def on_after_state_transition(self, p): raise RuntimeError("crash!")

        class GoodPlugin:
            name = "good"
            def on_after_state_transition(self, p): good_calls.append("ok")

        mgr.register(BadPlugin())
        mgr.register(GoodPlugin())

        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")

        # 触发 bad 熔断
        mgr.call("on_after_state_transition", payload)
        mgr.call("on_after_state_transition", payload)
        mgr.call("on_after_state_transition", payload)  # bad 已熔断

        # good 应该每次都被调用（不受 bad 影响）
        assert len(good_calls) == 3


# ---------------------------------------------------------------------------
# 未知钩子名处理
# ---------------------------------------------------------------------------

class TestUnknownHookName:
    def test_unknown_hook_returns_none(self):
        mgr = make_manager()
        result = mgr.call("non_existent_hook", None)
        assert result is None


class TestUiSafeExecutionPolicy:
    def test_handler_runs_in_caller_thread(self):
        mgr = make_manager()
        caller_thread = threading.get_ident()
        handler_threads: list[int] = []

        class ProbePlugin:
            name = "probe"

            def on_after_state_transition(self, payload):
                handler_threads.append(threading.get_ident())

        mgr.register(ProbePlugin())
        mgr.call("on_after_state_transition", AfterTransitionPayload(old_state="ghost", new_state="pulse"))

        assert handler_threads == [caller_thread]

    def test_timeout_still_counts_as_failure_and_keeps_isolation(self):
        mgr = make_manager(hook_timeout=0.01, failure_threshold=1, recovery_timeout=60.0)
        good_calls: list[str] = []

        class SlowPlugin:
            name = "slow"

            def on_after_state_transition(self, payload):
                time.sleep(0.02)

        class GoodPlugin:
            name = "good"

            def on_after_state_transition(self, payload):
                good_calls.append("ok")

        mgr.register(SlowPlugin())
        mgr.register(GoodPlugin())

        payload = AfterTransitionPayload(old_state="ghost", new_state="pulse")
        mgr.call("on_after_state_transition", payload)
        mgr.call("on_after_state_transition", payload)

        # slow 插件超时后被熔断，但 good 插件持续执行
        assert len(good_calls) == 2
