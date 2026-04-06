"""Windows-targeted HUD entrypoint."""

from __future__ import annotations

import sys

from flow_hud.core.config import HudConfig
from flow_hud.runtime import RUNTIME_WINDOWS, run_hud


def main() -> int:
    config = HudConfig.load()
    return run_hud(
        runtime_profile=RUNTIME_WINDOWS,
        config=config,
        discover_plugins=False,
    )


if __name__ == "__main__":
    sys.exit(main())
