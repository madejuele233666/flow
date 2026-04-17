from __future__ import annotations

from pathlib import Path

from flow_hud.core.config import HUD_CONFIG_FILENAME, HudConfig


def test_default_config_path_keeps_hud_data_dir_alignment_explicit() -> None:
    data_dir = Path("/tmp/flow-hud")

    assert HudConfig.default_config_path(data_dir) == data_dir / HUD_CONFIG_FILENAME


def test_load_uses_hud_data_dir_to_find_hud_config_toml(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "hud-data"
    data_dir.mkdir()
    config_path = HudConfig.default_config_path(data_dir)
    config_path.write_text(
        "\n".join(
            [
                "[hud]",
                f'data_dir = "{(tmp_path / "mismatched").as_posix()}"',
                "",
                "[connection]",
                'transport = "unix"',
                'socket_path = "/tmp/flow.sock"',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HUD_DATA_DIR", str(data_dir))

    config = HudConfig.load()

    assert config.data_dir == data_dir
    assert config.connection_transport == "unix"
    assert config.connection_socket_path == "/tmp/flow.sock"
