"""CLI 入口 — flow 命令集.

此模块只负责"接收用户输入 → 调用 FlowClient → 格式化输出"。
所有业务逻辑均由 FlowClient 适配器处理（本地直连 or IPC 远程）。

Phase 4.6: 六边形架构重构 — CLI 层彻底与领域层解耦。
CLI 不再直接触碰 repo / engine，统一通过 FlowClient Protocol 交互。

命令一览：
    flow add       — 添加新任务
    flow ls        — 列出任务（按引力排序）
    flow start     — 开始任务（自动压栈）
    flow status    — 查看当前活跃任务
    flow done      — 完成当前任务
    flow pause     — 暂停当前任务
    flow block     — 阻塞任务
    flow resume    — 恢复任务
    flow breakdown — [AI] 拆解任务
    flow export    — 导出任务数据
    flow templates — 模板管理
    flow plugins   — 插件管理
    flow daemon    — 守护进程管理 (start/stop/status)
    flow tui       — 启动沉浸式终端监控面板
"""

from __future__ import annotations

import sys
import asyncio
from datetime import datetime

import asyncclick as click

from flow_engine.client import FlowClient, create_client
from flow_engine.state.machine import TaskState


# ---------------------------------------------------------------------------
# 主命令组
# ---------------------------------------------------------------------------

class FlowGroup(click.Group):
    """自定义 Group 以支持懒加载插件命令."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._plugins_loaded = False

    def list_commands(self, ctx):
        if not self._plugins_loaded:
            _discover_plugin_commands(self)
            self._plugins_loaded = True
        return super().list_commands(ctx)

    def get_command(self, ctx, cmd_name):
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        if not self._plugins_loaded:
            _discover_plugin_commands(self)
            self._plugins_loaded = True
            return super().get_command(ctx, cmd_name)
        return None


@click.group(cls=FlowGroup)
@click.version_option(package_name="flow-engine")
@click.pass_context
async def main(ctx: click.Context) -> None:
    """心流引擎 (Flow Engine) — 用严苛的单任务协议对抗多任务焦虑."""
    # daemon / tui 子命令自行管理生命周期，跳过 FlowClient 初始化
    if ctx.invoked_subcommand in ("daemon", "tui"):
        return

    # Phase 4.6: 六边形架构 — 统一注入 FlowClient 端口
    client = await create_client()
    ctx.obj = client

    # 若 RemoteClient，注册关闭回调
    if hasattr(client, "close"):
        ctx.call_on_close(lambda: asyncio.ensure_future(client.close()))


# ---------------------------------------------------------------------------
# 插件命令自动发现
# ---------------------------------------------------------------------------

def _discover_plugin_commands(group: click.Group) -> None:
    """从 entry_points 发现并注册插件 CLI 命令."""
    try:
        if sys.version_info >= (3, 12):
            from importlib.metadata import entry_points
        else:
            from importlib.metadata import entry_points

        eps = entry_points()
        if hasattr(eps, "select"):
            cmd_eps = eps.select(group="flow_engine.commands")
        else:
            cmd_eps = eps.get("flow_engine.commands", [])

        for ep in cmd_eps:
            try:
                cmd = ep.load()
                if isinstance(cmd, click.BaseCommand):
                    group.add_command(cmd, ep.name)
            except Exception:
                pass  # 静默跳过加载失败的插件命令
    except Exception:
        pass


# ---------------------------------------------------------------------------
# flow add
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.argument("title")
@click.option("--ddl", default=None, help="截止日期 (YYYY-MM-DD)")
@click.option("--p", "priority", default=2, type=click.IntRange(0, 3), help="优先级 P0-P3")
@click.option("--tag", multiple=True, help="标签（可多次指定）")
@click.option("--template", "template_name", default=None, help="使用模板创建")
async def add(client: FlowClient, title: str, ddl: str | None, priority: int, tag: tuple[str, ...], template_name: str | None) -> None:
    """添加新任务."""
    try:
        result = await client.add_task(
            title=title,
            priority=priority,
            ddl=ddl,
            tags=list(tag) if tag else None,
            template_name=template_name,
        )
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)

    if "template" in result:
        for t in result["tasks"]:
            click.echo(f"  ✅ #{t['id']} [P{t['priority']}] {t['title']}")
        click.echo(f"📋 模板 [{result['template']}] 创建了 {len(result['tasks'])} 个任务")
    else:
        click.echo(f"✅ 已添加: #{result['id']} [P{result['priority']}] {title}")


# ---------------------------------------------------------------------------
# flow ls
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.option("--all", "show_all", is_flag=True, help="显示全部任务（含已完成/取消）")
@click.option("--state", "filter_state", default=None, help="按状态筛选")
@click.option("--tag", "filter_tag", default=None, help="按标签筛选")
@click.option("--p", "filter_priority", default=None, help="按优先级筛选 (如 0-1)")
async def ls(client: FlowClient, show_all: bool, filter_state: str | None, filter_tag: str | None, filter_priority: str | None) -> None:
    """列出任务（按引力得分排序）."""
    try:
        ranked = await client.list_tasks(
            show_all=show_all,
            filter_state=filter_state,
            filter_tag=filter_tag,
            filter_priority=filter_priority,
        )
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)

    if not ranked:
        click.echo("📭 暂无匹配的任务")
        return

    click.echo("─" * 60)
    for i, t in enumerate(ranked):
        marker = "🔥" if i == 0 else "  "
        state_icon = _state_icon_str(t["state"])
        ddl_str = f" ⏰{t['ddl']}" if t.get("ddl") else ""
        click.echo(f"{marker} #{t['id']:>3} [P{t['priority']}] {state_icon} {t['title']}{ddl_str}")
    click.echo("─" * 60)


# ---------------------------------------------------------------------------
# flow start
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.argument("task_id", type=int)
async def start(client: FlowClient, task_id: int) -> None:
    """开始执行任务（自动暂停当前活跃任务）."""
    try:
        result = await client.start_task(task_id)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)

    for pid in result.get("paused", []):
        click.echo(f"⏸️  已自动暂停: #{pid}")

    if result.get("restored_window"):
        click.echo(f"📸 上次现场: {result['restored_window']}")

    click.echo(f"🚀 开始: #{result['id']} {result['title']}")


# ---------------------------------------------------------------------------
# flow status
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
async def status(client: FlowClient) -> None:
    """查看当前活跃任务与专注时长."""
    result = await client.get_status()
    active = result.get("active")
    if not active:
        click.echo("😴 当前没有进行中的任务，使用 flow start <id> 开始")
        return

    duration = ""
    if active.get("duration_min") is not None:
        duration = f" | ⏱️ 已专注 {active['duration_min']} 分钟"

    click.echo(f"🎯 #{active['id']} [P{active['priority']}] {active['title']}{duration}")

    if result.get("break_suggested"):
        click.echo("☕ 建议休息一下！你已经持续专注超过阈值了。")


# ---------------------------------------------------------------------------
# flow done
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
async def done(client: FlowClient) -> None:
    """完成当前活跃任务."""
    try:
        result = await client.done_task()
    except ValueError as e:
        click.echo(f"❌ {e}")
        return
    click.echo(f"🎉 已完成: #{result['id']} {result['title']}")


# ---------------------------------------------------------------------------
# flow pause
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
async def pause(client: FlowClient) -> None:
    """暂停当前活跃任务."""
    try:
        result = await client.pause_task()
    except ValueError as e:
        click.echo(f"❌ {e}")
        return
    click.echo(f"⏸️  已暂停: #{result['id']} {result['title']}")


# ---------------------------------------------------------------------------
# flow block
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.argument("task_id", type=int)
@click.option("--reason", default="", help="阻塞原因")
async def block(client: FlowClient, task_id: int, reason: str) -> None:
    """将任务标记为阻塞状态."""
    try:
        result = await client.block_task(task_id, reason=reason)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)
    msg = f"🚧 已阻塞: #{result['id']} {result['title']}"
    if result.get("reason"):
        msg += f" (原因: {result['reason']})"
    click.echo(msg)


# ---------------------------------------------------------------------------
# flow resume
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.argument("task_id", type=int)
async def resume(client: FlowClient, task_id: int) -> None:
    """恢复暂停或阻塞的任务."""
    try:
        result = await client.resume_task(task_id)
    except ValueError as e:
        click.echo(f"❌ {e}")
        return
    click.echo(f"▶️  已恢复: #{result['id']} {result['title']} → {result['state']}")


# ---------------------------------------------------------------------------
# flow mount / unmount / mounts
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.argument("path_or_url", required=False)
@click.option("--note", default="", help="附加备注；留空时可创建 note-only mount")
@click.option("--task", "task_id", default=None, type=int, help="目标任务 ID；默认当前活跃任务")
async def mount(client: FlowClient, path_or_url: str | None, note: str, task_id: int | None) -> None:
    """挂载文件、URL 或备注到任务."""
    try:
        item = await client.add_mount(path_or_url, note=note, task_id=task_id)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)
    target = item.get("path") or item.get("url") or item.get("note") or "(empty)"
    click.echo(f"📎 已挂载: {item['id']} [{item['kind']}] {target}")


@main.command("unmount")
@click.pass_obj
@click.argument("mount_id")
@click.option("--task", "task_id", default=None, type=int, help="目标任务 ID；默认当前活跃任务")
async def unmount(client: FlowClient, mount_id: str, task_id: int | None) -> None:
    """移除任务挂载项."""
    try:
        removed = await client.remove_mount(mount_id, task_id=task_id)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)
    if not removed:
        click.echo(f"❌ 未找到挂载项: {mount_id}")
        raise SystemExit(1)
    click.echo(f"🗑️  已移除挂载项: {mount_id}")


@main.command("mounts")
@click.pass_obj
@click.option("--task", "task_id", default=None, type=int, help="目标任务 ID；默认当前活跃任务")
async def mounts_cmd(client: FlowClient, task_id: int | None) -> None:
    """列出任务挂载项."""
    try:
        items = await client.list_mounts(task_id=task_id)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)

    if not items:
        click.echo("📭 当前任务没有挂载项")
        return

    for item in items:
        target = item.get("path") or item.get("url") or item.get("note") or "(empty)"
        pinned = " pinned" if item.get("pinned") else ""
        click.echo(f"📎 {item['id']} [{item['kind']}] {target}{pinned}")


# ---------------------------------------------------------------------------
# flow breakdown
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.argument("task_id", type=int)
async def breakdown(client: FlowClient, task_id: int) -> None:
    """[AI] 拆解任务为小步骤."""
    try:
        steps = await client.breakdown_task(task_id)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)
    click.echo(f"📋 任务拆解: #{task_id}")
    for i, step in enumerate(steps, 1):
        click.echo(f"  {i}. {step}")


# ---------------------------------------------------------------------------
# flow export
# ---------------------------------------------------------------------------

@main.command()
@click.pass_obj
@click.option("--format", "fmt", default="json", help="导出格式 (json / csv)")
@click.option("--all", "show_all", is_flag=True, help="包含已完成/取消的任务")
async def export(client: FlowClient, fmt: str, show_all: bool) -> None:
    """导出任务数据."""
    try:
        output = await client.export_tasks(fmt=fmt, show_all=show_all)
    except ValueError as e:
        click.echo(f"❌ {e}")
        raise SystemExit(1)
    click.echo(output)


# ---------------------------------------------------------------------------
# flow templates — 通过 FlowClient 协议访问
# ---------------------------------------------------------------------------

@main.group()
async def templates() -> None:
    """任务模板管理."""


@templates.command("ls")
async def templates_ls() -> None:
    """列出可用模板."""
    client = await create_client()
    all_templates = await client.list_templates()
    if not all_templates:
        click.echo("📭 暂无可用模板")
        return
    click.echo("📋 可用模板：")
    for name, desc in all_templates:
        click.echo(f"  • {name:20s} — {desc}")


# ---------------------------------------------------------------------------
# flow plugins — 通过 FlowClient 协议访问
# ---------------------------------------------------------------------------

@main.group()
async def plugins() -> None:
    """插件管理."""


@plugins.command("ls")
async def plugins_ls() -> None:
    """列出已注册插件."""
    client = await create_client()
    all_plugins = await client.list_plugins()
    if not all_plugins:
        click.echo("📭 暂无已注册插件")
        return
    click.echo("🔌 已注册插件：")
    for p in all_plugins:
        click.echo(f"  • {p['name']} v{p['version']} — {p['description']}")


# ---------------------------------------------------------------------------
# flow daemon (Phase 3: Ghost Daemon 生命周期管理)
# ---------------------------------------------------------------------------

@main.group()
async def daemon() -> None:
    """守护进程管理 — 启动/停止/查询 Ghost Daemon."""


@daemon.command("start")
async def daemon_start() -> None:
    """启动 Ghost Daemon（后台常驻服务）."""
    from flow_engine.daemon import FlowDaemon

    if FlowDaemon.is_running():
        click.secho("⚡ Daemon 已在运行中", fg="yellow")
        return

    import subprocess

    # 以子进程方式启动 Daemon，脱离当前终端
    proc = subprocess.Popen(
        [sys.executable, "-m", "flow_engine.daemon"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # 完全脱离父进程
    )
    click.secho(f"🚀 Daemon 已启动 (PID {proc.pid})", fg="green")


@daemon.command("stop")
async def daemon_stop() -> None:
    """停止运行中的 Ghost Daemon."""
    from flow_engine.daemon import FlowDaemon

    if not FlowDaemon.is_running():
        click.secho("💤 Daemon 未运行", fg="yellow")
        return

    if FlowDaemon.stop_running():
        click.secho("🛑 已向 Daemon 发送停止信号", fg="green")
    else:
        click.secho("❌ 发送停止信号失败", fg="red")


@daemon.command("status")
async def daemon_status() -> None:
    """查看 Ghost Daemon 运行状态."""
    from flow_engine.daemon import FlowDaemon

    if FlowDaemon.is_running():
        click.secho("🟢 Daemon 运行中", fg="green")
    else:
        click.secho("🔴 Daemon 未运行", fg="red")


# ---------------------------------------------------------------------------
# flow tui (Phase 3: 沉浸式终端监控面板)
# ---------------------------------------------------------------------------

@main.command()
async def tui() -> None:
    """启动沉浸式 TUI 终端监控面板."""
    from flow_engine.hud.tui import run_tui
    run_tui()


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _state_icon_str(state_value: str) -> str:
    """状态值字符串对应的终端图标."""
    return {
        "Draft": "📝",
        "Ready": "⬜",
        "Scheduled": "📅",
        "In Progress": "🔵",
        "Paused": "⏸️ ",
        "Blocked": "🚧",
        "Done": "✅",
        "Canceled": "❌",
    }.get(state_value, "❓")


def cli_runner() -> None:
    """带有全局边界异常捕获的运行器."""
    try:
        main(_anyio_backend="asyncio")
    except Exception as e:
        import sys
        click.secho(f"🔥 系统内部异常/流程中止: {str(e)}", fg="red", err=True)
        sys.exit(2)


if __name__ == "__main__":
    cli_runner()
