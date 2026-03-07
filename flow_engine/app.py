"""应用编排器 (App Orchestrator) — 组装全部模块的唯一入口.

设计要点：
- 依赖注入容器：在此处创建所有模块实例并注入依赖。
- 工厂模式：通过配置字符串解析具体实现类，不硬编码 import。
- 其他模块互不感知彼此的存在，全部通过此处组装 + 事件总线通信。
- 测试时可替换任意组件为 mock。

Phase 4 升级：
- HookManager 接收配置化的超时/熔断阈值（零 Magic Numbers）
- PluginContext 替代直接暴露 FlowApp 给插件
- MarkdownTaskRepository 支持文件锁
- safe_mode / --safe-mode 全局跳过第三方插件

Phase 5 升级：
- BackgroundEventWorker 驱动非关键路径事件（通知、快照等）
- 通知事件改为后台 Fire-and-Forget，绝不阻塞主业务
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from flow_engine.config import AppConfig, load_config
from flow_engine.context.aw_plugin import ActivityWatchPlugin
from flow_engine.context.base_plugin import ContextService, SnapshotManager
from flow_engine.events import BackgroundEventWorker, EventBus, EventType
from flow_engine.hooks import HookManager
from flow_engine.notifications.base import NotificationService, NotifyLevel
from flow_engine.notifications.terminal import TerminalNotifier
from flow_engine.plugins.context import AdminContext, PluginContext
from flow_engine.plugins.registry import PluginRegistry
from flow_engine.scheduler.factors import CompositeRanker, build_default_factors
from flow_engine.scheduler.gravity import StubAdvisor, StubBreaker
from flow_engine.state.transitions import TransitionEngine
from flow_engine.storage.base import TaskRepository, VersionControl
from flow_engine.storage.exporters import CsvExporter, ExporterRegistry, JsonExporter
from flow_engine.storage.git_ledger import GitLedger
from flow_engine.storage.frontmatter_io import FrontmatterTaskRepository
from flow_engine.storage.markdown_io import MarkdownTaskRepository
from flow_engine.templates.base import TemplateRegistry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 工厂注册表 — 通过配置字符串解析实现类
# ---------------------------------------------------------------------------

_STORAGE_BACKENDS: dict[str, type] = {
    "markdown": MarkdownTaskRepository,
    "frontmatter": FrontmatterTaskRepository,
}

_NOTIFIER_BACKENDS: dict[str, type] = {
    "terminal": TerminalNotifier,
    # 未来: "webhook": WebhookNotifier, "telegram": TelegramNotifier
}


def _create_repo(config: AppConfig) -> TaskRepository:
    """工厂方法：根据配置创建存储后端."""
    backend = config.storage.backend
    cls = _STORAGE_BACKENDS.get(backend)
    if cls is None:
        logger.warning("unknown storage backend '%s', falling back to markdown", backend)
        cls = MarkdownTaskRepository

    # 如果是 MarkdownTaskRepository, 注入文件锁配置
    if cls is MarkdownTaskRepository:
        return cls(
            config.paths.tasks_path,
            lock_enabled=config.file_lock.enabled,
            lock_timeout=config.file_lock.timeout_seconds,
        )
    return cls(config.paths.tasks_path)


def _create_notifiers(config: AppConfig) -> list:
    """工厂方法：根据配置创建通知后端列表."""
    notifiers = []
    for name in config.notifications.backends:
        cls = _NOTIFIER_BACKENDS.get(name)
        if cls:
            notifiers.append(cls())
        else:
            logger.warning("unknown notification backend: %s", name)
    return notifiers


class FlowApp:
    """心流引擎的顶层编排器.

    职责：
    1. 加载配置
    2. 实例化所有模块并注入依赖
    3. 连接事件总线 + 钩子系统
    4. 通过 PluginContext 安全初始化插件
    5. 暴露统一的服务属性供 CLI 调用

    用法:
        app = FlowApp()               # 使用默认配置
        app = FlowApp(custom_config)   # 使用自定义配置（测试用）
    """

    def __init__(self, config: AppConfig | None = None) -> None:
        # ── 配置 ──
        self.config = config or load_config()
        breaker_cfg = self.config.plugin_breaker

        # ── 后台事件工作器 (Phase 5: 非关键路径的 Fire-and-Forget) ──
        self._bg_worker = BackgroundEventWorker(max_retries=2)
        self._bg_worker.start()

        # ── 事件总线（解耦核心，注入后台工作器） ──
        self.bus = EventBus(background_worker=self._bg_worker)

        # ── 钩子系统（pluggy 模式 + 熔断器保护） ──
        # 全部阈值从 PluginBreakerConfig 注入，零 Magic Numbers
        self.hooks = HookManager(
            hook_timeout=breaker_cfg.hook_timeout_seconds,
            failure_threshold=breaker_cfg.failure_threshold,
            recovery_timeout=breaker_cfg.recovery_timeout_seconds,
            safe_mode=breaker_cfg.safe_mode,
            dev_mode=breaker_cfg.dev_mode,
        )

        # ── 存储层（工厂模式 + 文件锁） ──
        self.repo: TaskRepository = _create_repo(self.config)
        self.vcs: VersionControl = GitLedger(
            self.config.paths.data_dir,
            enabled=self.config.git.enabled,
        )

        # ── 状态机层（注入钩子管理器） ──
        self.engine = TransitionEngine(self.bus, hook_mgr=self.hooks)

        # ── 上下文捕获层 ──
        snapshot_mgr = SnapshotManager(self.config.paths.snapshots_path)
        self.context = ContextService(snapshot_mgr)
        if self.config.context.enabled:
            self.context.register(
                ActivityWatchPlugin(self.config.context.activitywatch_url)
            )

        # ── 调度层（组合式排序器） ──
        self.ranker = CompositeRanker(
            factors=build_default_factors(
                priority_weight=self.config.scheduler.priority_weight,
                ddl_weight=self.config.scheduler.ddl_weight,
                dependency_weight=self.config.scheduler.dependency_weight,
            ),
        )
        self.breaker = StubBreaker()
        self.advisor = StubAdvisor(self.ranker)

        # ── 通知系统 ──
        self.notifications = NotificationService()
        if self.config.notifications.enabled:
            for notifier in _create_notifiers(self.config):
                self.notifications.register(notifier)

        # ── 导出器注册表 ──
        self.exporters = ExporterRegistry()
        self.exporters.register(JsonExporter())
        self.exporters.register(CsvExporter())

        # ── 模板系统 ──
        self.templates = TemplateRegistry()
        self.templates.register_builtins()
        self.templates.load_user_templates(self.config.paths.templates_path)

        # ── 构建 PluginContext（标准沙盒） ──
        self.plugin_context = PluginContext(
            config=self.config,
            hooks=self.hooks,
            notifications=self.notifications,
            exporters=self.exporters,
            ranker=self.ranker,
            templates=self.templates,
        )

        # ── 构建 AdminContext（高权限沙盒，受信任插件专用） ──
        self.admin_context = AdminContext(
            config=self.config,
            hooks=self.hooks,
            notifications=self.notifications,
            exporters=self.exporters,
            ranker=self.ranker,
            templates=self.templates,
            engine=self.engine,
            event_bus=self.bus,
        )

        # ── 插件自动发现（最后执行，通过双轨上下文分发） ──
        self.plugins = PluginRegistry()
        if not breaker_cfg.safe_mode:
            self.plugins.discover()
            self.plugins.setup_all(
                ctx=self.plugin_context,
                admin_ctx=self.admin_context,
                admin_names=breaker_cfg.admin_plugins,
            )

        # ── 事件连线 ──
        self._wire_events()

        logger.info("FlowApp initialized, data_dir=%s", self.config.paths.data_dir)

    def _wire_events(self) -> None:
        """连接跨模块的事件处理器."""
        self.bus.subscribe(EventType.TASK_STATE_CHANGED, self._on_state_changed)
        # 通知在非关键路径，使用后台事件广播
        if self.config.notifications.enabled:
            self.bus.subscribe(EventType.TASK_STATE_CHANGED, self._on_notify_bg)
        # 上下文捕获走后台队列 — 绝不阻塞主业务
        if self.config.context.capture_on_switch:
            self.bus.subscribe(EventType.TASK_STATE_CHANGED, self._on_capture_context_bg)

    async def _on_state_changed(self, event) -> None:
        """响应状态变更：持久化 + 版本控制."""
        tasks = await self.repo.load_all()
        await self.repo.save_all(tasks)
        if self.config.git.auto_commit:
            p = event.payload
            state_val = p.new_state.value if hasattr(p.new_state, "value") else str(p.new_state)
            await asyncio.to_thread(self.vcs.commit, f"{self.config.git.commit_prefix} task #{p.task_id} → {state_val}")

    def _on_notify_bg(self, event) -> None:
        """状态变更自动通知 — 同步回调，由后台 Worker 驱动."""
        p = event.payload
        state_val = p.new_state.value if hasattr(p.new_state, "value") else str(p.new_state)
        self.notifications.notify(
            title="状态变更",
            body=f"任务 #{p.task_id} → {state_val}",
            level=NotifyLevel.INFO,
        )

    async def shutdown(self) -> None:
        """优雅关闭 — 清理插件资源并等待后台队列排空."""
        self.plugins.teardown_all()
        await self._bg_worker.stop()

    def _on_capture_context_bg(self, event) -> None:
        """状态变更时异步捕获上下文快照 — 由后台 Worker 驱动.

        这是一个同步回调，但实际的 async capture 由
        BackgroundEventWorker 在其消费循环中异步执行。
        """
        task_id = event.payload.task_id if event.payload else None
        if task_id is not None:
            # 利用 ensure_future 启动异步捕获，不阻塞当前事件回调
            asyncio.ensure_future(self.context.capture_async(task_id))

    # ── 工厂注册 API（供插件扩展） ──

    @staticmethod
    def register_storage_backend(name: str, cls: type) -> None:
        """注册自定义存储后端（插件调用）."""
        _STORAGE_BACKENDS[name] = cls

    @staticmethod
    def register_notifier_backend(name: str, cls: type) -> None:
        """注册自定义通知后端（插件调用）."""
        _NOTIFIER_BACKENDS[name] = cls
