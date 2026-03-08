"""HUD 插件元信息 (Plugin Manifest).

对标主引擎 plugins/registry.py → PluginManifest — 完整复刻声明式元数据模式。

用法:
    from flow_hud.plugins.manifest import HudPluginManifest

    class MyPlugin(HudPlugin):
        manifest = HudPluginManifest(
            name=\"my-plugin\",
            version=\"1.0.0\",
            description=\"我的 HUD 插件\",
            author=\"作者名\",
        )
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class HudPluginManifest:
    """声明式 HUD 插件元数据（类似 package.json / manifest.json）.

    对标主引擎 PluginManifest — 完整 6 字段复刻。
    frozen=True 确保元数据不可变，防止运行时篡改。
    """

    name: str
    version: str = "0.1.0"
    description: str = ""
    author: str = ""
    requires: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] = field(default_factory=dict)
