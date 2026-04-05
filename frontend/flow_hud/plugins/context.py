"""HUD 插件沙盒环境 (Plugin Context).

对标主引擎 plugins/context.py → PluginContext + AdminContext — 完整双层结构复刻。

设计要点:
- HudPluginContext（普通沙盒）：只暴露注册型 API，防止插件访问底层内部状态。
- HudAdminContext（高权限超集）：在普通沙盒基础上，额外以只读 @property Any 暴露
  底层引用（state_machine, event_bus, hook_manager），防止覆写，避免循环 import。
- 底层引用一律用 Any 类型注释，禁止在此文件中 import 具体类。

用法（插件侧）:
    class MyPlugin(HudPlugin):
        def setup(self, ctx: HudPluginContext) -> None:
            ctx.subscribe_event(HudEventType.MOUSE_GLOBAL_MOVE, self.on_mouse)
            ctx.register_hook(self)
            cfg = ctx.get_extension_config(\"my-plugin\")

    class AdminPlugin(HudPlugin):
        def setup(self, ctx: HudAdminContext) -> None:
            # 高权限：可访问底层引用
            self._sm = ctx.state_machine
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flow_hud.core.config import HudConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 协议定义 — 强类型契约
# ---------------------------------------------------------------------------

@runtime_checkable
class HudHookRegistrar(Protocol):
    """HUD 钩子注册协议 (对标 flow_engine.HookRegistrar)."""

    def register(self, implementor: object) -> list[str]: ...
    def unregister(self, implementor: object) -> None: ...


@runtime_checkable
class HudEventBusRegistrar(Protocol):
    """HUD 事件总线注册协议 (插件侧沙盒)."""

    def subscribe(self, event_type: Any, handler: Callable) -> None: ...
    def unsubscribe(self, event_type: Any, handler: Callable) -> None: ...
    def emit(self, event_type: Any, payload: Any = None) -> None: ...
    def emit_background(self, event_type: Any, payload: Any = None) -> None: ...


@runtime_checkable
class HudStateMachineProtocol(Protocol):
    """HUD 状态机契约 (插件侧沙盒)."""

    @property
    def current_state(self) -> Any: ...  # 返回 HudState 枚举，但避免显式依赖

    def transition(self, target: Any) -> tuple[Any, Any]: ...


# ---------------------------------------------------------------------------
# HudPluginContext — 普通沙盒
# ---------------------------------------------------------------------------

class HudPluginContext:
    """普通插件的安全沙盒 — 只暴露注册型 API.

    对标主引擎 PluginContext — 功能映射：
    - subscribe_event  ← EventBus.subscribe
    - register_widget  ← 向 UI canvas 注册小部件
    - register_hook    ← HookManager.register
    - get_extension_config ← config.extensions.get
    - data_dir / safe_mode ← 只读配置属性

    底层引用（hooks, event_bus）通过 Protocol 注入，实现防泄漏。
    禁止在此文件中 import 具体类，避免循环依赖。
    """

    def __init__(
        self,
        config: HudConfig,
        hooks: HudHookRegistrar,
        event_bus: HudEventBusRegistrar,
    ) -> None:
        self._config = config
        self._hooks = hooks
        self._event_bus = event_bus
        # UI 画布注册表：name → widget（Any，避免 PySide6 依赖）
        self._widgets: dict[str, Any] = {}

    @property
    def event_bus(self) -> HudEventBusRegistrar:
        """事件总线访问器（受限制的 Protocol）."""
        return self._event_bus

    # ── 注册 API ──

    def subscribe_event(self, event_type: Any, handler: Callable) -> None:
        """注册事件监听器（委托 EventBus）."""
        self._event_bus.subscribe(event_type, handler)

    def unsubscribe_event(self, event_type: Any, handler: Callable) -> None:
        """移除事件监听器."""
        self._event_bus.unsubscribe(event_type, handler)

    def register_widget(self, name: str, widget: Any) -> None:
        """向 UI 画布注册小部件.

        Args:
            name: 小部件名称（唯一标识符）
            widget: Qt 小部件实例（QWidget 或其子类）
        """
        if name in self._widgets:
            logger.warning("widget %r already registered, overwriting", name)
        self._widgets[name] = widget
        logger.debug("widget registered: %r", name)

    def register_hook(self, implementor: object) -> list[str]:
        """注册钩子实现（委托 HookManager）.

        Returns:
            成功注册的钩子名列表。
        """
        return self._hooks.register(implementor)

    def unregister_hook(self, implementor: object) -> None:
        """移除钩子实现."""
        self._hooks.unregister(implementor)

    def get_extension_config(self, plugin_name: str) -> dict[str, Any]:
        """获取插件专属配置（从 [extensions.xxx] 透传）.

        返回空字典如果没有配置，不会抛出异常。
        """
        return self._config.extensions.get(plugin_name, {})

    def get_connection_config(self) -> dict[str, Any]:
        """获取 HUD 连接默认配置（来自 [connection]）。"""
        return {
            "transport": self._config.connection_transport,
            "host": self._config.connection_host,
            "port": self._config.connection_port,
            "socket_path": self._config.connection_socket_path,
        }

    # ── 只读配置 ──

    @property
    def data_dir(self) -> Path:
        """数据目录（只读）."""
        return self._config.data_dir

    @property
    def safe_mode(self) -> bool:
        """是否处于安全模式."""
        return self._config.safe_mode

    # ── 内部工具（供 HudApp 访问）──

    def get_widgets(self) -> dict[str, Any]:
        """返回已注册的全部小部件（供 UI 画布消费）."""
        return dict(self._widgets)


# ---------------------------------------------------------------------------
# HudAdminContext — 高权限沙盒
# ---------------------------------------------------------------------------

class HudAdminContext(HudPluginContext):
    """受信任插件的高权限沙盒 — HudPluginContext 的超集.

    对标主引擎 AdminContext(PluginContext) — 适配：
    - 主引擎暴露 engine（TransitionEngine），HUD 暴露 state_machine（HudStateMachine）
    - 额外开放 hook_manager 引用（主引擎无此字段，HUD 新增以支持高级工具插件）

    设计要点：
    - 纯子类，只做加法，完全兼容 HudPluginContext 类型注解。
    - 底层引用一律只读 @property，并使用 Protocol 强化类型安全。
    - TYPE_CHECKING 延迟导入，零运行时耦合（防循环 import）。
    """

    def __init__(
        self,
        config: HudConfig,
        hooks: HudHookRegistrar,
        event_bus: HudEventBusRegistrar,
        *,
        state_machine: HudStateMachineProtocol | None = None,
        hook_manager: HudHookRegistrar | None = None,
    ) -> None:
        super().__init__(config=config, hooks=hooks, event_bus=event_bus)
        self._state_machine = state_machine
        self._hook_manager = hook_manager

    @property
    def state_machine(self) -> HudStateMachineProtocol | None:
        """HUD 状态机（只读，Protocol 契约）."""
        return self._state_machine

    @property
    def hook_manager(self) -> HudHookRegistrar | None:
        """钩子管理器（只读，Protocol 契约）."""
        return self._hook_manager
