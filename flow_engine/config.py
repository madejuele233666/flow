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

    data_dir: Path = field(default_factory=lambda: Path.home() / ".flow_engine")
    tasks_file: str = "tasks.md"  # 相对于 data_dir
    snapshots_dir: str = "snapshots"
    templates_dir: str = "templates"

    @property
    def templates_path(self) -> Path:
        return self.data_dir / self.templates_dir

    @property
    def tasks_path(self) -> Path:
        return self.data_dir / self.tasks_file

    @property
    def snapshots_path(self) -> Path:
        return self.data_dir / self.snapshots_dir


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

    backend: str = "markdown"  # markdown | json | 自定义


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

    # 确保数据目录存在
    config.paths.data_dir.mkdir(parents=True, exist_ok=True)
    config.paths.snapshots_path.mkdir(parents=True, exist_ok=True)

    return config
