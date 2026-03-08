"""Tests for HudStateMachine — 覆盖所有合法路径和非法路径.

对标 design.md Decision 6 的规格要求。
"""

import pytest

from flow_hud.core.state_machine import (
    HudState,
    HudStateMachine,
    IllegalTransitionError,
    TRANSITIONS,
    can_transition,
)


# ---------------------------------------------------------------------------
# can_transition 工具函数测试
# ---------------------------------------------------------------------------

class TestCanTransition:
    def test_ghost_to_pulse_allowed(self):
        assert can_transition(HudState.GHOST, HudState.PULSE) is True

    def test_ghost_to_command_not_allowed(self):
        assert can_transition(HudState.GHOST, HudState.COMMAND) is False

    def test_ghost_to_ghost_not_allowed(self):
        assert can_transition(HudState.GHOST, HudState.GHOST) is False

    def test_pulse_to_ghost_allowed(self):
        assert can_transition(HudState.PULSE, HudState.GHOST) is True

    def test_pulse_to_command_allowed(self):
        assert can_transition(HudState.PULSE, HudState.COMMAND) is True

    def test_pulse_to_pulse_not_allowed(self):
        assert can_transition(HudState.PULSE, HudState.PULSE) is False

    def test_command_to_ghost_allowed(self):
        assert can_transition(HudState.COMMAND, HudState.GHOST) is True

    def test_command_to_pulse_allowed(self):
        assert can_transition(HudState.COMMAND, HudState.PULSE) is True

    def test_command_to_command_not_allowed(self):
        assert can_transition(HudState.COMMAND, HudState.COMMAND) is False


# ---------------------------------------------------------------------------
# TRANSITIONS 白名单结构测试
# ---------------------------------------------------------------------------

class TestTransitionsWhitelist:
    def test_all_states_in_whitelist(self):
        """每个 HudState 都必须在 TRANSITIONS 白名单中。"""
        for state in HudState:
            assert state in TRANSITIONS, f"{state} missing from TRANSITIONS"

    def test_transitions_are_frozensets(self):
        for state, targets in TRANSITIONS.items():
            assert isinstance(targets, frozenset), f"{state} targets must be frozenset"

    def test_ghost_targets(self):
        assert TRANSITIONS[HudState.GHOST] == frozenset({HudState.PULSE})

    def test_pulse_targets(self):
        assert TRANSITIONS[HudState.PULSE] == frozenset({HudState.GHOST, HudState.COMMAND})

    def test_command_targets(self):
        assert TRANSITIONS[HudState.COMMAND] == frozenset({HudState.GHOST, HudState.PULSE})


# ---------------------------------------------------------------------------
# HudStateMachine 合法路径测试
# ---------------------------------------------------------------------------

class TestHudStateMachineValidPaths:
    def setup_method(self):
        self.sm = HudStateMachine()

    def test_initial_state_is_ghost(self):
        assert self.sm.current_state == HudState.GHOST

    def test_ghost_to_pulse(self):
        old, new = self.sm.transition(HudState.PULSE)
        assert old == HudState.GHOST
        assert new == HudState.PULSE
        assert self.sm.current_state == HudState.PULSE

    def test_pulse_to_command(self):
        self.sm.transition(HudState.PULSE)
        old, new = self.sm.transition(HudState.COMMAND)
        assert old == HudState.PULSE
        assert new == HudState.COMMAND
        assert self.sm.current_state == HudState.COMMAND

    def test_command_to_pulse(self):
        self.sm.transition(HudState.PULSE)
        self.sm.transition(HudState.COMMAND)
        old, new = self.sm.transition(HudState.PULSE)
        assert old == HudState.COMMAND
        assert new == HudState.PULSE

    def test_command_to_ghost(self):
        self.sm.transition(HudState.PULSE)
        self.sm.transition(HudState.COMMAND)
        old, new = self.sm.transition(HudState.GHOST)
        assert old == HudState.COMMAND
        assert new == HudState.GHOST

    def test_pulse_to_ghost(self):
        self.sm.transition(HudState.PULSE)
        old, new = self.sm.transition(HudState.GHOST)
        assert old == HudState.PULSE
        assert new == HudState.GHOST

    def test_full_cycle_ghost_pulse_command_ghost(self):
        """完整生命周期路径：GHOST → PULSE → COMMAND → GHOST"""
        self.sm.transition(HudState.PULSE)
        self.sm.transition(HudState.COMMAND)
        old, new = self.sm.transition(HudState.GHOST)
        assert new == HudState.GHOST

    def test_transition_returns_tuple(self):
        result = self.sm.transition(HudState.PULSE)
        assert isinstance(result, tuple)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# HudStateMachine 非法路径测试
# ---------------------------------------------------------------------------

class TestHudStateMachineIllegalPaths:
    def setup_method(self):
        self.sm = HudStateMachine()

    def test_ghost_to_command_raises(self):
        with pytest.raises(IllegalTransitionError) as exc_info:
            self.sm.transition(HudState.COMMAND)
        assert "ghost" in str(exc_info.value).lower()
        assert "command" in str(exc_info.value).lower()

    def test_ghost_to_ghost_raises(self):
        with pytest.raises(IllegalTransitionError):
            self.sm.transition(HudState.GHOST)

    def test_pulse_to_pulse_raises(self):
        self.sm.transition(HudState.PULSE)
        with pytest.raises(IllegalTransitionError):
            self.sm.transition(HudState.PULSE)

    def test_command_to_command_raises(self):
        self.sm.transition(HudState.PULSE)
        self.sm.transition(HudState.COMMAND)
        with pytest.raises(IllegalTransitionError):
            self.sm.transition(HudState.COMMAND)

    def test_illegal_transition_error_has_correct_attrs(self):
        err = IllegalTransitionError(HudState.GHOST, HudState.COMMAND)
        assert err.current == HudState.GHOST
        assert err.target == HudState.COMMAND

    def test_illegal_transition_error_message_contains_allowed_states(self):
        """错误信息必须包含合法目标状态（方便调试）。"""
        err = IllegalTransitionError(HudState.GHOST, HudState.COMMAND)
        # GHOST 只能去 PULSE，所以错误消息应提示 pulse
        assert "pulse" in str(err).lower()

    def test_state_unchanged_after_illegal_transition(self):
        """非法转换不能改变当前状态。"""
        assert self.sm.current_state == HudState.GHOST
        with pytest.raises(IllegalTransitionError):
            self.sm.transition(HudState.COMMAND)
        assert self.sm.current_state == HudState.GHOST  # 状态不变


# ---------------------------------------------------------------------------
# HudStateMachine 工具方法测试
# ---------------------------------------------------------------------------

class TestHudStateMachineUtils:
    def test_reset(self):
        sm = HudStateMachine()
        sm.transition(HudState.PULSE)
        sm.reset()
        assert sm.current_state == HudState.GHOST

    def test_reset_to_specific_state(self):
        sm = HudStateMachine()
        sm.reset(HudState.COMMAND)
        assert sm.current_state == HudState.COMMAND

    def test_repr(self):
        sm = HudStateMachine()
        r = repr(sm)
        assert "ghost" in r
