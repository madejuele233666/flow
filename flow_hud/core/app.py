"""HUD 应用编排器 (App Orchestrator) — 配置驱动的 DI 组装工厂.

对标主引擎 app.py → FlowApp — 严格复刻组装顺序和 shutdown 模式。

组装顺序（对标 FlowApp.__init__）:
    1. 加载配置 (HudConfig)
    2. 启动后台 Worker (HudBackgroundEventWorker)
    3. 初始化 EventBus（注入 Worker）
    4. 初始化 HookManager（注入阈值）
    5. 初始化状态机 (HudStateMachine)
    6. 初始化插件注册表 (HudPluginRegistry)
    7. 构造双层沙盒 (HudPluginContext + HudAdminContext)
    8. 插件发现 + 分级 setup（按 admin_names 白名单）
    9. 事件连线 (_wire_events)

用法:
    app = HudApp()                # 使用默认配置
    app = HudApp(custom_config)   # 使用自定义配置（测试用）
    # ...
    app.shutdown()                # 优雅关闭
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from flow_hud.core.config import HudConfig
from flow_hud.core.events import HudBackgroundEventWorker, HudEventBus, HudEventType
from flow_hud.core.hooks import HudHookManager
from flow_hud.core.state_machine import HudState, HudStateMachine
from flow_hud.plugins.context import HudAdminContext, HudPluginContext
from flow_hud.plugins.registry import HudPluginRegistry

if TYPE_CHECKING:
    from flow_hud.plugins.base import HudPlugin

logger = logging.getLogger(__name__)


class HudApp:
    """HUD 顶层编排器 — 配置驱动的 DI 组装工厂.

    对标主引擎 FlowApp — 职责：
    1. 加载配置
    2. 实例化所有模块并注入依赖
    3. 连接事件总线
    4. 通过双层 PluginContext 安全初始化插件
    5. 暴露统一的服务属性

    测试时可传入 custom_config 替换任意组件。
    """

    def __init__(self, config: HudConfig | None = None) -> None:
        # ── 1. 配置 ──
        self.config = config or HudConfig.load()

        # ── 2. 后台事件工作器（先启动，EventBus 依赖它） ──
        self._bg_worker = HudBackgroundEventWorker(
            max_retries=self.config.worker_max_retries,
        )
        self._bg_worker.start()

        # ── 3. 事件总线（注入后台工作器） ──
        self.event_bus = HudEventBus(background_worker=self._bg_worker)

        # ── 4. 钩子系统（注入全部阈值，零 Magic Numbers） ──
        self.hook_manager = HudHookManager(
            hook_timeout=self.config.hook_timeout,
            failure_threshold=self.config.failure_threshold,
            recovery_timeout=self.config.recovery_timeout,
            safe_mode=self.config.safe_mode,
            dev_mode=self.config.dev_mode,
        )

        # ── 5. 状态机（纯数据层） ──
        self.state_machine = HudStateMachine()

        # ── 6. 插件注册表 ──
        self.plugins = HudPluginRegistry()

        # ── 7. 双层沙盒上下文 ──
        self.plugin_context = HudPluginContext(
            config=self.config,
            hooks=self.hook_manager,
            event_bus=self.event_bus,
        )
        self.admin_context = HudAdminContext(
            config=self.config,
            hooks=self.hook_manager,
            event_bus=self.event_bus,
            state_machine=self.state_machine,
            hook_manager=self.hook_manager,
        )

        # ── 8. 插件自动发现 + 分级 setup ──
        if not self.config.safe_mode:
            self.plugins.discover()
        self.plugins.setup_all(
            ctx=self.plugin_context,
            admin_ctx=self.admin_context,
            admin_names=self.config.admin_plugins,
        )

        # ── 9. 事件连线 ──
        self._wire_events()

        logger.info(
            "HudApp initialized (plugins=%d, safe_mode=%s, data_dir=%s)",
            len(self.plugins.names()),
            self.config.safe_mode,
            self.config.data_dir,
        )

    def shutdown(self) -> None:
        """优雅关闭 — 对标 FlowApp.shutdown().

        执行顺序（与启动顺序相反）：
        1. 插件逆序 teardown（释放插件资源）
        2. BackgroundEventWorker 停止（等待队列排空）
        """
        logger.info("HudApp shutting down...")
        self.plugins.teardown_all()
        self._bg_worker.stop()
        logger.info("HudApp shutdown complete")

    def _wire_events(self) -> None:
        """连接跨模块事件处理器.

        对标 FlowApp._wire_events()。
        STATE_TRANSITIONED → 触发 hook_manager.call(\"on_after_state_transition\", ...)
        """
        self.event_bus.subscribe(
            HudEventType.STATE_TRANSITIONED,
            self._on_state_transitioned,
        )

    def _on_state_transitioned(self, event) -> None:
        """响应状态转变完成事件：通知所有插件的 on_after_state_transition 钩子."""
        from flow_hud.core.hooks_payload import AfterTransitionPayload

        payload = event.payload
        if payload is None:
            return

        hook_payload = AfterTransitionPayload(
            old_state=payload.old_state if hasattr(payload, "old_state") else "",
            new_state=payload.new_state if hasattr(payload, "new_state") else "",
        )
        self.hook_manager.call("on_after_state_transition", hook_payload)
