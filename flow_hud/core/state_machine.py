"""HUD 状态机 — 三态白名单守门 (State Machine).

对标主引擎 state/machine.py — 完全复刻白名单守门模式，适配 HUD 三态。

HUD 三态模型:
    GHOST   → 鼠标静止，HUD 完全隐形
    PULSE   → 鼠标接近感应区，HUD 浮现
    COMMAND → 用户长驻或主动激活，HUD 全功能展开

设计要点:
- TRANSITIONS 字典是「白名单」模式 — 只有显式声明的转移才合法。
- 非法转换立即抛出 IllegalTransitionError（携带允许的目标状态信息）。
- HudStateMachine 是纯 Python 数据逻辑，零 PySide6 依赖，可在无 GUI 环境全量测试。

【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。
"""

from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# 状态枚举
# ---------------------------------------------------------------------------

class HudState(str, Enum):
    """HUD 三态模型."""

    GHOST   = "ghost"    # 鼠标静止，HUD 完全隐形
    PULSE   = "pulse"    # 鼠标接近感应区，HUD 浮现
    COMMAND = "command"  # 用户长驻或主动激活，HUD 全功能展开


# ---------------------------------------------------------------------------
# 状态转移白名单
#
# key   = 当前状态
# value = 该状态允许转移到的目标状态集合
# ---------------------------------------------------------------------------

TRANSITIONS: dict[HudState, frozenset[HudState]] = {
    HudState.GHOST:   frozenset({HudState.PULSE}),
    HudState.PULSE:   frozenset({HudState.GHOST, HudState.COMMAND}),
    HudState.COMMAND: frozenset({HudState.GHOST, HudState.PULSE}),
}


def can_transition(current: HudState, target: HudState) -> bool:
    """判断从 current 到 target 的转移是否合法."""
    return target in TRANSITIONS.get(current, frozenset())


# ---------------------------------------------------------------------------
# 错误类型
# ---------------------------------------------------------------------------

class IllegalTransitionError(Exception):
    """非法状态转移异常.

    携带当前状态、目标状态和所有合法目标状态的信息。
    """

    def __init__(self, current: HudState, target: HudState) -> None:
        self.current = current
        self.target = target
        allowed = ", ".join(s.value for s in TRANSITIONS.get(current, frozenset()))
        super().__init__(
            f"非法转移: {current.value} → {target.value}。"
            f"当前状态 [{current.value}] 允许转移到: [{allowed or '无 (终态)'}]"
        )


# ---------------------------------------------------------------------------
# 状态机
# ---------------------------------------------------------------------------

class HudStateMachine:
    """HUD 三态状态机.

    持有当前状态，通过白名单 TRANSITIONS 守门。
    所有状态变化必须经过此模块校验，禁止任何模块绕过状态机直接修改状态。
    """

    def __init__(self, initial: HudState = HudState.GHOST) -> None:
        self._current: HudState = initial

    @property
    def current_state(self) -> HudState:
        """当前 HUD 状态（只读）."""
        return self._current

    def transition(self, target: HudState) -> tuple[HudState, HudState]:
        """校验合法性后执行状态转换.

        Args:
            target: 目标状态枚举值

        Returns:
            (old_state, new_state) 二元组

        Raises:
            IllegalTransitionError: 目标状态不在当前状态的白名单中
        """
        if not can_transition(self._current, target):
            raise IllegalTransitionError(self._current, target)
        old = self._current
        self._current = target
        return old, target

    def reset(self, state: HudState = HudState.GHOST) -> None:
        """强制重置到指定状态（仅供测试使用）."""
        self._current = state

    def __repr__(self) -> str:
        return f"HudStateMachine(current={self._current.value!r})"
