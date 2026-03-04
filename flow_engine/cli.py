"""CLI 入口 — flow 命令集.

此模块只负责"接收用户输入 → 调用 app 服务 → 格式化输出"。
所有业务逻辑均由 FlowApp 及其内部模块处理。

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
"""

from __future__ import annotations

import sys
import asyncio
from datetime import datetime

import asyncclick as click

from flow_engine.app import FlowApp
from flow_engine.state.machine import TaskState
from flow_engine.storage.task_model import Task

# 延迟初始化，避免每次 --help 都加载全部模块
_app: FlowApp | None = None


def _get_app() -> FlowApp:
    global _app
    if _app is None:
        _app = FlowApp()
    return _app


# ---------------------------------------------------------------------------
# 主命令组
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(package_name="flow-engine")
async def main() -> None:
    """心流引擎 (Flow Engine) — 用严苛的单任务协议对抗多任务焦虑."""


# ---------------------------------------------------------------------------
# 插件命令自动发现
# ---------------------------------------------------------------------------

def _discover_plugin_commands() -> None:
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
                    main.add_command(cmd, ep.name)
            except Exception:
                pass  # 静默跳过加载失败的插件命令
    except Exception:
        pass


_discover_plugin_commands()


# ---------------------------------------------------------------------------
# flow add
# ---------------------------------------------------------------------------

@main.command()
@click.argument("title")
@click.option("--ddl", default=None, help="截止日期 (YYYY-MM-DD)")
@click.option("--p", "priority", default=2, type=click.IntRange(0, 3), help="优先级 P0-P3")
@click.option("--tag", multiple=True, help="标签（可多次指定）")
@click.option("--template", "template_name", default=None, help="使用模板创建")
async def add(title: str, ddl: str | None, priority: int, tag: tuple[str, ...], template_name: str | None) -> None:
    """添加新任务."""
    app = _get_app()

    if template_name:
        # 模板模式
        tmpl = app.templates.get(template_name)
        if tmpl is None:
            click.echo(f"❌ 未找到模板: {template_name}")
            click.echo(f"可用模板: {', '.join(n for n, _ in app.templates.list_all())}")
            raise SystemExit(1)
        base_id = await app.repo.next_id()
        output = tmpl.create(
            base_id=base_id,
            title=title,
            priority=priority,
            ddl=datetime.strptime(ddl, "%Y-%m-%d") if ddl else None,
        )
        tasks = await app.repo.load_all()
        tasks.extend(output.tasks)
        await app.repo.save_all(tasks)
        if app.config.git.auto_commit:
            await asyncio.to_thread(app.vcs.commit, f"{app.config.git.commit_prefix} add template:{template_name}")
        for t in output.tasks:
            click.echo(f"  ✅ #{t.id} [P{t.priority}] {t.title}")
        click.echo(f"📋 模板 [{template_name}] 创建了 {len(output.tasks)} 个任务")
        return

    task = Task(
        id=await app.repo.next_id(),
        title=title,
        priority=priority,
        ddl=datetime.strptime(ddl, "%Y-%m-%d") if ddl else None,
        tags=list(tag),
    )
    tasks = await app.repo.load_all()
    tasks.append(task)
    await app.repo.save_all(tasks)
    if app.config.git.auto_commit:
        await asyncio.to_thread(app.vcs.commit, f"{app.config.git.commit_prefix} add #{task.id} {task.title}")

    click.echo(f"✅ 已添加: #{task.id} [P{priority}] {title}")


# ---------------------------------------------------------------------------
# flow ls
# ---------------------------------------------------------------------------

@main.command()
@click.option("--all", "show_all", is_flag=True, help="显示全部任务（含已完成/取消）")
@click.option("--state", "filter_state", default=None, help="按状态筛选")
@click.option("--tag", "filter_tag", default=None, help="按标签筛选")
@click.option("--p", "filter_priority", default=None, help="按优先级筛选 (如 0-1)")
async def ls(show_all: bool, filter_state: str | None, filter_tag: str | None, filter_priority: str | None) -> None:
    """列出任务（按引力得分排序）."""
    app = _get_app()
    tasks = await app.repo.load_all()

    # 应用过滤器
    from flow_engine.storage.filters import TaskFilter
    tf = TaskFilter(tasks)

    if not show_all:
        tf = tf.exclude_terminal()

    if filter_state:
        try:
            state = TaskState(filter_state.replace("_", " ").title())
            tf = tf.by_state(state)
        except ValueError:
            click.echo(f"❌ 未知状态: {filter_state}")
            raise SystemExit(1)

    if filter_tag:
        tf = tf.by_tag(filter_tag)

    if filter_priority:
        if "-" in filter_priority:
            lo, hi = filter_priority.split("-", 1)
            tf = tf.by_priority(int(lo), int(hi))
        else:
            p = int(filter_priority)
            tf = tf.by_priority(p, p)

    filtered = tf.results()
    ranked = app.ranker.rank(filtered) if filtered else []

    if not ranked:
        click.echo("📭 暂无匹配的任务")
        return

    click.echo("─" * 60)
    for i, t in enumerate(ranked):
        marker = "🔥" if i == 0 else "  "
        state_icon = _state_icon(t.state)
        ddl_str = f" ⏰{t.ddl:%m-%d}" if t.ddl else ""
        click.echo(f"{marker} #{t.id:>3} [P{t.priority}] {state_icon} {t.title}{ddl_str}")
    click.echo("─" * 60)


# ---------------------------------------------------------------------------
# flow start
# ---------------------------------------------------------------------------

@main.command()
@click.argument("task_id", type=int)
async def start(task_id: int) -> None:
    """开始执行任务（自动暂停当前活跃任务）."""
    app = _get_app()
    tasks = await app.repo.load_all()
    task = _find_task(tasks, task_id)

    paused = await app.engine.ensure_single_active(tasks, task_id)
    for p in paused:
        click.echo(f"⏸️  已自动暂停: #{p.id} {p.title}")
        if app.config.context.capture_on_switch:
            await asyncio.to_thread(app.context.capture, p.id)

    await app.engine.transition(task, TaskState.IN_PROGRESS)
    task.started_at = datetime.now()
    await app.repo.save_all(tasks)

    snapshot = await asyncio.to_thread(app.context.restore_latest, task_id)
    if snapshot and snapshot.active_window:
        click.echo(f"📸 上次现场: {snapshot.active_window}")

    click.echo(f"🚀 开始: #{task.id} {task.title}")


# ---------------------------------------------------------------------------
# flow status
# ---------------------------------------------------------------------------

@main.command()
async def status() -> None:
    """查看当前活跃任务与专注时长."""
    app = _get_app()
    active = await app.repo.get_active()
    if not active:
        click.echo("😴 当前没有进行中的任务，使用 flow start <id> 开始")
        return

    duration = ""
    if active.started_at:
        delta = datetime.now() - active.started_at
        minutes = int(delta.total_seconds() // 60)
        duration = f" | ⏱️ 已专注 {minutes} 分钟"

    click.echo(f"🎯 #{active.id} [P{active.priority}] {active.title}{duration}")

    if active.started_at:
        elapsed_min = (datetime.now() - active.started_at).total_seconds() / 60
        if elapsed_min >= app.config.focus.break_interval_minutes:
            click.echo("☕ 建议休息一下！你已经持续专注超过阈值了。")


# ---------------------------------------------------------------------------
# flow done
# ---------------------------------------------------------------------------

@main.command()
async def done() -> None:
    """完成当前活跃任务."""
    app = _get_app()
    tasks = await app.repo.load_all()
    active = next((t for t in tasks if t.is_active), None)
    if not active:
        click.echo("❌ 当前没有进行中的任务")
        return

    await app.engine.transition(active, TaskState.DONE)
    await app.repo.save_all(tasks)
    click.echo(f"🎉 已完成: #{active.id} {active.title}")


# ---------------------------------------------------------------------------
# flow pause
# ---------------------------------------------------------------------------

@main.command()
async def pause() -> None:
    """暂停当前活跃任务."""
    app = _get_app()
    tasks = await app.repo.load_all()
    active = next((t for t in tasks if t.is_active), None)
    if not active:
        click.echo("❌ 当前没有进行中的任务")
        return

    if app.config.context.capture_on_switch:
        await asyncio.to_thread(app.context.capture, active.id)

    await app.engine.transition(active, TaskState.PAUSED)
    await app.repo.save_all(tasks)
    click.echo(f"⏸️  已暂停: #{active.id} {active.title}")


# ---------------------------------------------------------------------------
# flow block
# ---------------------------------------------------------------------------

@main.command()
@click.argument("task_id", type=int)
@click.option("--reason", default="", help="阻塞原因")
async def block(task_id: int, reason: str) -> None:
    """将任务标记为阻塞状态."""
    app = _get_app()
    tasks = await app.repo.load_all()
    task = _find_task(tasks, task_id)

    await app.engine.transition(task, TaskState.BLOCKED)
    task.block_reason = reason
    await app.repo.save_all(tasks)
    click.echo(f"🚧 已阻塞: #{task.id} {task.title}" + (f" (原因: {reason})" if reason else ""))


# ---------------------------------------------------------------------------
# flow resume
# ---------------------------------------------------------------------------

@main.command()
@click.argument("task_id", type=int)
async def resume(task_id: int) -> None:
    """恢复暂停或阻塞的任务."""
    app = _get_app()
    tasks = await app.repo.load_all()
    task = _find_task(tasks, task_id)

    if task.state == TaskState.BLOCKED:
        await app.engine.transition(task, TaskState.READY)
        task.block_reason = ""
        await app.repo.save_all(tasks)
        click.echo(f"🔓 已解除阻塞: #{task.id}，使用 flow start {task.id} 继续")
    elif task.state == TaskState.PAUSED:
        paused = await app.engine.ensure_single_active(tasks, task_id)
        for p in paused:
            click.echo(f"⏸️  已自动暂停: #{p.id} {p.title}")
        await app.engine.transition(task, TaskState.IN_PROGRESS)
        task.started_at = datetime.now()
        await app.repo.save_all(tasks)
        click.echo(f"▶️  已恢复: #{task.id} {task.title}")
    else:
        click.echo(f"❌ 任务 #{task.id} 当前状态为 {task.state.value}，无法恢复")


# ---------------------------------------------------------------------------
# flow breakdown
# ---------------------------------------------------------------------------

@main.command()
@click.argument("task_id", type=int)
async def breakdown(task_id: int) -> None:
    """[AI] 拆解任务为小步骤."""
    app = _get_app()
    task = _find_task(await app.repo.load_all(), task_id)
    steps = app.breaker.breakdown(task)
    click.echo(f"📋 任务拆解: #{task.id} {task.title}")
    for i, step in enumerate(steps, 1):
        click.echo(f"  {i}. {step}")


# ---------------------------------------------------------------------------
# flow export
# ---------------------------------------------------------------------------

@main.command()
@click.option("--format", "fmt", default="json", help="导出格式 (json / csv)")
@click.option("--all", "show_all", is_flag=True, help="包含已完成/取消的任务")
async def export(fmt: str, show_all: bool) -> None:
    """导出任务数据."""
    app = _get_app()
    exporter = app.exporters.get(fmt)
    if exporter is None:
        click.echo(f"❌ 未知格式: {fmt}")
        click.echo(f"可用格式: {', '.join(app.exporters.list_formats())}")
        raise SystemExit(1)

    tasks = await app.repo.load_all()
    if not show_all:
        tasks = [t for t in tasks if not t.is_terminal]

    output = exporter.export(tasks)
    click.echo(output)


# ---------------------------------------------------------------------------
# flow templates
# ---------------------------------------------------------------------------

@main.group()
async def templates() -> None:
    """任务模板管理."""


@templates.command("ls")
async def templates_ls() -> None:
    """列出可用模板."""
    app = _get_app()
    all_templates = app.templates.list_all()
    if not all_templates:
        click.echo("📭 暂无可用模板")
        return
    click.echo("📋 可用模板：")
    for name, desc in all_templates:
        click.echo(f"  • {name:20s} — {desc}")


# ---------------------------------------------------------------------------
# flow plugins
# ---------------------------------------------------------------------------

@main.group()
async def plugins() -> None:
    """插件管理."""


@plugins.command("ls")
async def plugins_ls() -> None:
    """列出已注册插件."""
    app = _get_app()
    names = app.plugins.names()
    if not names:
        click.echo("📭 暂无已注册插件")
        return
    click.echo("🔌 已注册插件：")
    for name in names:
        plugin = app.plugins.get(name)
        if plugin:
            click.echo(f"  • {name} v{plugin.manifest.version} — {plugin.manifest.description}")


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _find_task(tasks: list[Task], task_id: int) -> Task:
    """按 ID 查找任务，找不到则退出."""
    task = next((t for t in tasks if t.id == task_id), None)
    if task is None:
        click.echo(f"❌ 未找到任务 #{task_id}")
        raise SystemExit(1)
    return task


def _state_icon(state: TaskState) -> str:
    """状态对应的终端图标."""
    return {
        TaskState.DRAFT: "📝",
        TaskState.READY: "⬜",
        TaskState.SCHEDULED: "📅",
        TaskState.IN_PROGRESS: "🔵",
        TaskState.PAUSED: "⏸️ ",
        TaskState.BLOCKED: "🚧",
        TaskState.DONE: "✅",
        TaskState.CANCELED: "❌",
    }.get(state, "❓")


if __name__ == "__main__":
    main(_anyio_backend="asyncio")
