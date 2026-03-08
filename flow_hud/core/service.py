"""HUD 端口契约层 (Port Contract — Service Protocol).

对标主引擎 client.py → FlowClient(Protocol) + LocalClient — 完整复刻防漏模式。

设计要点:
- HudServiceProtocol: @runtime_checkable，所有方法入参只允许 str/int/dict 基础类型，
  返回值只允许 dict 或 list[dict]，杜绝领域模型（HudState 枚举、QWidget 对象）泄漏。
- HudLocalService: 直连 HudApp 的本地适配器。将内部领域对象「剥皮」为纯 dict 输出。

用法:
    service = HudLocalService(app)
    state = service.get_hud_state()    # → {\"state\": \"ghost\", \"active_plugins\": [...]}
    result = service.transition_to(\"pulse\")  # → {\"old_state\": \"ghost\", \"new_state\": \"pulse\"}

    # 类型检查（运行时）
    assert isinstance(service, HudServiceProtocol)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flow_hud.core.app import HudApp

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HudServiceProtocol — 端口契约
# ---------------------------------------------------------------------------

@runtime_checkable
class HudServiceProtocol(Protocol):
    """HUD 对外暴露的唯一操控契约.

    对标主引擎 FlowClient(Protocol) — 端口防泄漏核心：
    - @runtime_checkable 支持 isinstance() 运行时检查
    - 所有方法入参只允许 str, int, dict 基础类型
    - 所有方法返回值只允许 dict 或 list[dict]
    - 严禁传入 QWidget、HudState 等域内对象

    方法语义:
        get_hud_state()           → 查询当前 HUD 状态摘要
        transition_to(target)     → 触发状态转换（target 为字符串如 \"pulse\"）
        register_widget(name, slot) → 声明 UI 插槽预占（纯字符串约定）
        list_plugins()            → 列出所有已注册插件
    """

    def get_hud_state(self) -> dict[str, Any]: ...

    def transition_to(self, target: str) -> dict[str, Any]: ...

    def register_widget(self, name: str, slot: str) -> dict[str, Any]: ...

    def list_plugins(self) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# HudLocalService — 本地直连适配器（「剥皮」模式）
# ---------------------------------------------------------------------------

class HudLocalService:
    """直连 HudApp 的本地适配器 — 将内部对象「剥皮」为 dict.

    对标主引擎 LocalClient — 「剥皮」模式核心：
    - 接收 HudApp 实例，调用其内部领域对象。
    - 所有返回值在此处转为纯 dict（HudState.value、plugin.name 等）。
    - 调用方（CLI、测试、外部工具）永远拿不到领域对象原始引用。
    """

    def __init__(self, app: HudApp) -> None:
        self._app = app

    def get_hud_state(self) -> dict[str, Any]:
        """查询当前 HUD 状态.

        Returns:
            {\"state\": str, \"active_plugins\": list[str]}
        """
        state = self._app.state_machine.current_state
        return {
            "state": state.value,
            "active_plugins": self._app.plugins.names(),
        }

    def transition_to(self, target: str) -> dict[str, Any]:
        """触发 HUD 状态转换.

        Args:
            target: 目标状态字符串（\"ghost\" / \"pulse\" / \"command\"）

        Returns:
            {\"old_state\": str, \"new_state\": str}

        Raises:
            ValueError: target 不是合法的 HudState 值
            IllegalTransitionError: 非法状态转换（将错误消息包装进 dict 返回）
        """
        from flow_hud.core.state_machine import HudState, IllegalTransitionError

        try:
            target_state = HudState(target)
        except ValueError:
            raise ValueError(f"无效的目标状态: {target!r}，合法值: {[s.value for s in HudState]}")

        try:
            old, new = self._app.state_machine.transition(target_state)
            return {"old_state": old.value, "new_state": new.value}
        except IllegalTransitionError as e:
            raise ValueError(str(e)) from e

    def register_widget(self, name: str, slot: str) -> dict[str, Any]:
        """声明 UI 插槽占位（纯字符串契约，供外部工具预先声明布局）.

        Args:
            name: 小部件唯一名称
            slot: 目标插槽位置字符串（如 \"top_right\", \"center\"）

        Returns:
            {\"name\": str, \"slot\": str, \"registered\": bool}
        """
        # 在此层仅做声明记录；实际 Qt 小部件由插件通过 ctx.register_widget() 注册
        logger.debug("register_widget: name=%r slot=%r", name, slot)
        return {"name": name, "slot": slot, "registered": True}

    def list_plugins(self) -> list[dict[str, Any]]:
        """列出所有已注册插件.

        Returns:
            [{\"name\": str, \"version\": str, \"description\": str}, ...]
        """
        result = []
        for plugin in self._app.plugins.all():
            result.append({
                "name": plugin.manifest.name,
                "version": plugin.manifest.version,
                "description": plugin.manifest.description,
            })
        return result
