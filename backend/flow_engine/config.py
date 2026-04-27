"""配置管理 — 所有可调参数的单一来源.

职责：
- 从 ~/.flow_engine/config.toml 加载用户配置
- 提供类型安全的默认值
- 支持环境变量覆盖 (FLOW_xxx)

设计要点：
- 配置全部集中在此模块，其他模块通过依赖注入获取，不直接读文件。
- 路径、阈值等全部可配，杜绝硬编码。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from flow_engine.ipc.defaults import (
    IPC_DEFAULT_DATA_DIR_NAME,
    IPC_DEFAULT_HEARTBEAT_INTERVAL_MS,
    IPC_DEFAULT_HEARTBEAT_MISS_THRESHOLD,
    IPC_DEFAULT_MAX_FRAME_BYTES,
    IPC_DEFAULT_PID_NAME,
    IPC_DEFAULT_REQUEST_TIMEOUT_MS,
    IPC_DEFAULT_SOCKET_NAME,
    IPC_DEFAULT_TCP_HOST,
    IPC_DEFAULT_TCP_PORT,
)

# toml 在 Python 3.11+ 有标准库 tomllib（只读）
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    import toml as tomllib  # type: ignore[no-redef]  # fallback


# ---------------------------------------------------------------------------
# 配置数据结构（嵌套 dataclass = 类型安全 + IDE 补全）
# ---------------------------------------------------------------------------

@dataclass
class PathsConfig:
    """所有文件系统路径."""

    data_dir: Path = field(default_factory=lambda: Path.home() / IPC_DEFAULT_DATA_DIR_NAME)
    tasks_file: str = "tasks.md"  # 相对于 data_dir
    snapshots_dir: str = "snapshots"
    templates_dir: str = "templates"
    mounts_dir: str = "mounts"
    trails_dir: str = "trails"

    @property
    def templates_path(self) -> Path:
        return self.data_dir / self.templates_dir

    @property
    def tasks_path(self) -> Path:
        return self.data_dir / self.tasks_file

    @property
    def snapshots_path(self) -> Path:
        return self.data_dir / self.snapshots_dir

    @property
    def mounts_path(self) -> Path:
        return self.data_dir / self.mounts_dir

    @property
    def trails_path(self) -> Path:
        return self.data_dir / self.trails_dir


@dataclass
class GitConfig:
    """Git 自动提交配置."""

    enabled: bool = True
    auto_commit: bool = True
    commit_prefix: str = "flow:"


@dataclass
class FocusConfig:
    """专注计时 & 休息提醒."""

    break_interval_minutes: int = 45
    break_reminder_style: str = "gentle"  # gentle | firm | off


@dataclass
class AIConfig:
    """BYOK AI 接入配置."""

    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    breakdown_max_steps: int = 8


@dataclass
class ContextConfig:
    """桌面上下文捕获配置."""

    enabled: bool = True
    activitywatch_url: str = "http://localhost:5600"
    capture_on_switch: bool = True
    trail_enabled: bool = True
    mount_enabled: bool = True
    restore_execution_enabled: bool = False
    browser_restore_max_pages: int = 5
    browser_segment_lookback_minutes: int = 60
    browser_segment_gap_seconds: int = 5
    restore_command_timeout_seconds: float = 2.0
    trails_dir: str = "trails"
    mounts_dir: str = "mounts"


@dataclass
class SchedulerConfig:
    """引力排序算法参数."""

    priority_weight: float = 0.4
    ddl_weight: float = 0.4
    dependency_weight: float = 0.2


@dataclass
class NotificationsConfig:
    """通知系统配置."""

    enabled: bool = True
    backends: list[str] = field(default_factory=lambda: ["terminal"])
    webhook_url: str = ""


@dataclass
class StorageConfig:
    """存储后端配置."""

    backend: str = "frontmatter"  # frontmatter | markdown | 自定义


@dataclass
class PluginBreakerConfig:
    """插件熔断器配置 — 消灭 Magic Numbers.

    所有超时/阈值参数均通过此配置注入，不在业务代码中硬编码。
    对应 TOML 配置节: [plugins.breaker]
    """

    hook_timeout_seconds: float = 0.5          # 单次 Hook 执行超时
    failure_threshold: int = 5                 # 连续失败次数触发熔断
    recovery_timeout_seconds: float = 60.0     # 熔断后的恢复冷却期
    safe_mode: bool = False                    # 全局安全模式：跳过所有第三方插件
    dev_mode: bool = False                     # 开发者模式：插件异常直接抛出，不静默
    admin_plugins: list[str] = field(default_factory=list)  # 允许获得高权限沙盒的插件名


@dataclass
class FileLockConfig:
    """文件锁配置.

    对应 TOML 配置节: [file_lock]
    """

    enabled: bool = True
    timeout_seconds: float = 10.0              # 等待文件锁的超时时间


@dataclass
class IPCConfig:
    """IPC 服务配置 — Unix Socket + TCP.

    对应 TOML 配置节: [ipc]
    """

    tcp_host: str = IPC_DEFAULT_TCP_HOST   # TCP 监听地址 (0.0.0.0 允许和内网其他机器连接)
    tcp_port: int = IPC_DEFAULT_TCP_PORT   # TCP 监听端口
    max_frame_bytes: int = IPC_DEFAULT_MAX_FRAME_BYTES
    request_timeout_ms: int = IPC_DEFAULT_REQUEST_TIMEOUT_MS
    heartbeat_interval_ms: int = IPC_DEFAULT_HEARTBEAT_INTERVAL_MS
    heartbeat_miss_threshold: int = IPC_DEFAULT_HEARTBEAT_MISS_THRESHOLD


@dataclass
class DaemonConfig:
    """Ghost Daemon 配置.

    对应 TOML 配置节: [daemon]
    """

    socket_name: str = IPC_DEFAULT_SOCKET_NAME  # Unix Socket 文件名（相对于 data_dir）
    pid_name: str = IPC_DEFAULT_PID_NAME        # PID 文件名（相对于 data_dir）


@dataclass
class AppConfig:
    """应用顶层配置 — 聚合所有子配置."""

    paths: PathsConfig = field(default_factory=PathsConfig)
    git: GitConfig = field(default_factory=GitConfig)
    focus: FocusConfig = field(default_factory=FocusConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    plugin_breaker: PluginBreakerConfig = field(default_factory=PluginBreakerConfig)
    file_lock: FileLockConfig = field(default_factory=FileLockConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    ipc: IPCConfig = field(default_factory=IPCConfig)
    extensions: dict[str, Any] = field(default_factory=dict)  # 插件开放配置


# ---------------------------------------------------------------------------
# 配置加载
# ---------------------------------------------------------------------------

def _env_override(config: AppConfig) -> AppConfig:
    """用 FLOW_xxx 环境变量覆盖配置值."""
    if v := os.environ.get("FLOW_DATA_DIR"):
        config.paths.data_dir = Path(v)
    if v := os.environ.get("FLOW_AI_API_KEY"):
        config.ai.api_key = v
        config.ai.enabled = True
    if v := os.environ.get("FLOW_AI_BASE_URL"):
        config.ai.base_url = v
    if v := os.environ.get("FLOW_AI_MODEL"):
        config.ai.model = v
    return config


def _apply_dict(config: AppConfig, raw: dict[str, Any]) -> AppConfig:
    """将 TOML 字典递归映射到 dataclass 字段."""
    section_map: dict[str, Any] = {
        "paths": config.paths,
        "git": config.git,
        "focus": config.focus,
        "ai": config.ai,
        "context": config.context,
        "scheduler": config.scheduler,
        "notifications": config.notifications,
        "storage": config.storage,
        "plugin_breaker": config.plugin_breaker,
        "file_lock": config.file_lock,
        "daemon": config.daemon,
        "ipc": config.ipc,
    }
    # 开放式 extensions 透传（不做字段校验）
    if "extensions" in raw:
        config.extensions = raw["extensions"]
    for section_name, section_obj in section_map.items():
        if section_name in raw:
            for key, value in raw[section_name].items():
                if hasattr(section_obj, key):
                    # 特殊处理 Path 类型
                    if isinstance(getattr(section_obj, key), Path):
                        value = Path(value)
                    setattr(section_obj, key, value)
    return config


def load_config(config_path: Path | None = None) -> AppConfig:
    """加载配置，优先级: 环境变量 > toml 文件 > 默认值."""
    config = AppConfig()

    # 确定配置文件位置
    path = config_path or config.paths.data_dir / "config.toml"
    if path.exists():
        with open(path, "rb") as f:
            raw = tomllib.load(f)  # type: ignore[arg-type]
        config = _apply_dict(config, raw)

    config = _env_override(config)

    config.paths.mounts_dir = config.context.mounts_dir
    config.paths.trails_dir = config.context.trails_dir

    # 确保数据目录存在
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    config.paths.snapshots_path.mkdir(parents=True, exist_ok=True)
    config.paths.mounts_path.mkdir(parents=True, exist_ok=True)
    config.paths.trails_path.mkdir(parents=True, exist_ok=True)

    return config
