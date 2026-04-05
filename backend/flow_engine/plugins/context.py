"""PluginContext — 安全的插件沙盒环境.

设计来源：
- pluginlib: 插件通过受限接口与宿主交互
- Obsidian: 插件只能通过 this.app 暴露的 API 操作系统

目的：
替代直接将 FlowApp 全部内部状态暴露给第三方插件的做法。
PluginContext 只开放必要的、安全的注册 API 和只读配置,
防止插件越界修改底层属性（如 app.repo = None）。

用法（插件侧）：
    class MyPlugin(FlowPlugin):
        def setup(self, ctx: PluginContext) -> None:
            cfg = ctx.get_extension_config("my_plugin")
            ctx.register_hook(self)
            ctx.register_notifier(MyNotifier())
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from flow_engine.config import AppConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 协议定义 — 强类型契约
# ---------------------------------------------------------------------------

@runtime_checkable
class HookRegistrar(Protocol):
    """钩子注册协议."""
    def register(self, implementor: object) -> list[str]: ...
    def unregister(self, implementor: object) -> None: ...


@runtime_checkable
class NotifierRegistrar(Protocol):
    """通知后端注册协议."""
    def register(self, notifier: Any) -> None: ...


@runtime_checkable
class ExporterRegistrar(Protocol):
    """导出器注册协议."""
    def register(self, exporter: Any) -> None: ...


@runtime_checkable
class FactorRegistrar(Protocol):
    """排序因子注册协议."""
    def add_factor(self, factor: Any) -> None: ...


@runtime_checkable
class TemplateRegistrar(Protocol):
    """模板注册协议."""
    def register(self, template: Any) -> None: ...


# ---------------------------------------------------------------------------
# PluginContext — 安全沙盒
# ---------------------------------------------------------------------------

class PluginContext:
    """插件沙盒环境 — 只暴露安全的注册 API.

    插件通过此对象与宿主系统交互，而非直接持有 FlowApp 引用。
    所有属性均为只读或纯注册型 API，无法直接覆盖核心内部状态。
    """

    def __init__(
        self,
        config: AppConfig,
        hooks: HookRegistrar,
        notifications: NotifierRegistrar,
        exporters: ExporterRegistrar,
        ranker: FactorRegistrar,
        templates: TemplateRegistrar,
    ) -> None:
        self._config = config
        self._hooks = hooks
        self._notifications = notifications
        self._exporters = exporters
        self._ranker = ranker
        self._templates = templates

    # ── 只读配置 ──

    def get_extension_config(self, plugin_name: str) -> dict[str, Any]:
        """获取插件专属的配置（从 [extensions.xxx] 透传）.

        返回空字典如果没有配置。不会抛出异常。
        """
        return self._config.extensions.get(plugin_name, {})

    @property
    def data_dir(self):
        """数据目录（只读）."""
        return self._config.paths.data_dir

    @property
    def safe_mode(self) -> bool:
        """是否处于安全模式."""
        return self._config.plugin_breaker.safe_mode

    # ── 注册 API ──

    def register_hook(self, implementor: object) -> list[str]:
        """注册钩子实现."""
        return self._hooks.register(implementor)

    def unregister_hook(self, implementor: object) -> None:
        """移除钩子实现."""
        self._hooks.unregister(implementor)

    def register_notifier(self, notifier: Any) -> None:
        """注册通知后端."""
        self._notifications.register(notifier)

    def register_exporter(self, exporter: Any) -> None:
        """注册导出格式."""
        self._exporters.register(exporter)

    def register_factor(self, factor: Any) -> None:
        """注册排序因子."""
        self._ranker.add_factor(factor)

    def register_template(self, template: Any) -> None:
        """注册任务模板."""
        self._templates.register(template)


# ---------------------------------------------------------------------------
# AdminContext — 受信任插件的高权限沙盒
# ---------------------------------------------------------------------------

class AdminContext(PluginContext):
    """高权限沙盒 — PluginContext 的超集.

    仅面向「官方插件」或用户在 config.toml 中显式授权的第三方插件。
    在 PluginContext 全部安全 API 的基础上，额外开放底层控制流接口。

    设计要点：
    - 纯子类，只做加法，完全兼容 PluginContext 类型注解。
    - 依赖通过 TYPE_CHECKING 延迟导入，零运行时耦合。
    - 使用只读 @property 暴露，防止属性被插件覆写。

    用法（受信任插件侧）：
        class CoreAutoScheduler(FlowPlugin):
            def setup(self, ctx: AdminContext) -> None:
                # 高级 API: 直接访问 TransitionEngine
                self._engine = ctx.engine
                ctx.register_hook(self)
    """

    def __init__(
        self,
        config: AppConfig,
        hooks: HookRegistrar,
        notifications: NotifierRegistrar,
        exporters: ExporterRegistrar,
        ranker: FactorRegistrar,
        templates: TemplateRegistrar,
        *,
        engine: Any = None,
        event_bus: Any = None,
    ) -> None:
        super().__init__(config, hooks, notifications, exporters, ranker, templates)
        self._engine = engine
        self._event_bus = event_bus

    @property
    def engine(self) -> Any:
        """状态转移引擎（只读）.

        类型实际为 TransitionEngine，使用 Any 避免强运行时依赖。
        """
        return self._engine

    @property
    def event_bus(self) -> Any:
        """事件总线（只读）.

        类型实际为 EventBus，使用 Any 避免强运行时依赖。
        """
        return self._event_bus
