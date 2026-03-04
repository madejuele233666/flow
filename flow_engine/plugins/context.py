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
