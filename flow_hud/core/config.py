"""HUD 配置管理 (Config).

对标主引擎 config.py — 配置驱动 DI，消灭 Magic Numbers。

HudConfig 从 hud_config.toml 加载（位于 data_dir）；
支持环境变量 HUD_DATA_DIR 覆盖数据目录路径。

用法:
    config = HudConfig.load()          # 从 ~/.flow_hud/hud_config.toml 加载
    config = HudConfig.load(path)      # 从指定路径加载
    config = HudConfig()               # 使用默认值（测试用）
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


@dataclass
class HudConfig:
    """HUD 顶层配置 — 聚合所有可调参数.

    对标主引擎 AppConfig（适配 HUD 的具体需求）。

    配置节（hud_config.toml）:
        [hud]
        data_dir = \"~/.flow_hud\"

        [plugins]
        plugins = [\"ipc-bridge\", \"mouse-radar\"]
        admin_plugins = [\"ipc-bridge\"]
        safe_mode = false

        [hook_breaker]
        hook_timeout = 0.5
        failure_threshold = 5
        recovery_timeout = 60.0
        dev_mode = false

        [worker]
        max_retries = 2

        [extensions]
        [extensions.my-plugin]
        api_key = \"xxx\"
    """

    # ── 路径 ──
    data_dir: Path = field(default_factory=lambda: Path.home() / ".flow_hud")

    # ── 插件列表与权限 ──
    plugins: list[str] = field(default_factory=list)
    admin_plugins: list[str] = field(default_factory=list)
    safe_mode: bool = False

    # ── HookBreaker 阈值（零 Magic Numbers） ──
    hook_timeout: float = 0.5
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    dev_mode: bool = False

    # ── BackgroundEventWorker ──
    worker_max_retries: int = 2

    # ── 插件开放配置（透传） ──
    extensions: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: Path | None = None) -> HudConfig:
        """从 hud_config.toml 加载配置，优先级: 环境变量 > toml > 默认值."""
        config = cls()

        # 环境变量覆盖数据目录
        if env_dir := os.environ.get("HUD_DATA_DIR"):
            config.data_dir = Path(env_dir)

        path = config_path or (config.data_dir / "hud_config.toml")
        if path.exists():
            with open(path, "rb") as f:
                raw = tomllib.load(f)  # type: ignore[arg-type]
            config = cls._apply_dict(config, raw)

        # 确保数据目录存在
        config.data_dir.mkdir(parents=True, exist_ok=True)
        return config

    @classmethod
    def _apply_dict(cls, config: HudConfig, raw: dict[str, Any]) -> HudConfig:
        """将 TOML 字典映射到 HudConfig 字段."""
        if "hud" in raw:
            hud = raw["hud"]
            if "data_dir" in hud:
                config.data_dir = Path(hud["data_dir"]).expanduser()

        if "plugins" in raw:
            plugins_section = raw["plugins"]
            if "plugins" in plugins_section:
                config.plugins = list(plugins_section["plugins"])
            if "admin_plugins" in plugins_section:
                config.admin_plugins = list(plugins_section["admin_plugins"])
            if "safe_mode" in plugins_section:
                config.safe_mode = bool(plugins_section["safe_mode"])

        if "hook_breaker" in raw:
            hb = raw["hook_breaker"]
            if "hook_timeout" in hb:
                config.hook_timeout = float(hb["hook_timeout"])
            if "failure_threshold" in hb:
                config.failure_threshold = int(hb["failure_threshold"])
            if "recovery_timeout" in hb:
                config.recovery_timeout = float(hb["recovery_timeout"])
            if "dev_mode" in hb:
                config.dev_mode = bool(hb["dev_mode"])

        if "worker" in raw:
            if "max_retries" in raw["worker"]:
                config.worker_max_retries = int(raw["worker"]["max_retries"])

        if "extensions" in raw:
            config.extensions = raw["extensions"]

        return config
