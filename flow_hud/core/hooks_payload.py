"""强类型钩子载荷 (Typed Hook Payloads).

对标主引擎 hooks_payload.py — 按 mutability 契约区分 frozen vs mutable。
- Waterfall 钩子 → 可变 dataclass（插件可原地修改属性）
- BAIL_VETO 钩子 → frozen dataclass（插件返回 bool 投票）
- Parallel 钩子  → frozen dataclass（只读通知）

【防腐规定】该文件内严禁出现任何 PySide6 或外设相关的 import。

用法 (插件侧):
    class MyPlugin(HudPlugin):
        def before_state_transition(self, payload: BeforeTransitionPayload) -> None:
            # Waterfall: 原地修改目标状态
            if some_condition:
                payload.target_state = \"ghost\"

        def on_after_state_transition(self, payload: AfterTransitionPayload) -> None:
            # Parallel: 只读通知
            print(f\"{payload.old_state} → {payload.new_state}\")
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Waterfall 载荷 — 可变，插件可原地修改属性
# ---------------------------------------------------------------------------

@dataclass
class BeforeTransitionPayload:
    """before_state_transition (BAIL_VETO 前置 WATERFALL 变体) — 插件可修改 target_state.

    Mutable: 插件通过修改 target_state 属性来重定向目标状态。
    HookManager 将完整修改过的 payload 返回给调用方。
    """

    current_state: str   # HudState.value（只读，描述当前状态）
    target_state: str    # HudState.value（可修改，用于重定向目标状态）


@dataclass
class BeforeWidgetRegisterPayload:
    """before_widget_register (WATERFALL) — 插件可修改目标插槽.

    Mutable: 插件可通过修改 slot 属性将小部件重定向到不同的 UI 插槽。
    """

    name: str   # 小部件名称（只读）
    slot: str   # 目标插槽（可修改，如 \"top_right\" → \"center\"）


# ---------------------------------------------------------------------------
# BAIL_VETO 载荷 — 不可变，插件返回 bool 一票否决
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class VetoTransitionPayload:
    """before_state_transition (BAIL_VETO) — 插件返回 False 可一票否决状态转移.

    Frozen: 插件不可修改载荷；通过返回值（True=通过 / False=否决）投票。
    """

    current_state: str   # HudState.value
    target_state: str    # HudState.value


# ---------------------------------------------------------------------------
# Parallel 载荷 — 不可变，仅通知
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AfterTransitionPayload:
    """on_after_state_transition (PARALLEL) — 状态转移完成后的只读通知.

    Frozen: 插件只能读取，不可修改。
    """

    old_state: str   # HudState.value
    new_state: str   # HudState.value
