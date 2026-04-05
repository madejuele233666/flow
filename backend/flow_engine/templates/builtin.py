"""内置模板集 — 开箱即用的常见工作流."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from flow_engine.storage.task_model import Task
from flow_engine.templates.base import TaskTemplate, TemplateOutput


class WeeklyReviewTemplate(TaskTemplate):
    """每周复盘模板 — 创建回顾 + 规划两个子任务."""

    @property
    def name(self) -> str:
        return "weekly_review"

    @property
    def description(self) -> str:
        return "每周复盘：回顾本周 + 规划下周"

    def create(self, base_id: int, **overrides: Any) -> TemplateOutput:
        return TemplateOutput(tasks=[
            Task(
                id=base_id,
                title="📋 回顾本周完成的任务",
                priority=overrides.get("priority", 1),
                tags=["复盘", "每周"],
            ),
            Task(
                id=base_id + 1,
                title="📝 规划下周任务清单",
                priority=overrides.get("priority", 1),
                ddl=datetime.now() + timedelta(days=7),
                tags=["规划", "每周"],
                parent_id=base_id,
            ),
        ])


class StudySessionTemplate(TaskTemplate):
    """学习任务模板 — 预习 + 学习 + 复习三步骤."""

    @property
    def name(self) -> str:
        return "study_session"

    @property
    def description(self) -> str:
        return "学习任务：预习 → 学习 → 复习"

    def create(self, base_id: int, **overrides: Any) -> TemplateOutput:
        subject = overrides.get("subject", "待定科目")
        return TemplateOutput(tasks=[
            Task(
                id=base_id,
                title=f"📖 预习：{subject}",
                priority=2,
                tags=["学习", subject],
            ),
            Task(
                id=base_id + 1,
                title=f"✍️ 学习：{subject}",
                priority=1,
                tags=["学习", subject],
                parent_id=base_id,
            ),
            Task(
                id=base_id + 2,
                title=f"🔄 复习：{subject}",
                priority=2,
                ddl=datetime.now() + timedelta(days=3),
                tags=["学习", "复习", subject],
                parent_id=base_id,
            ),
        ])


class QuickTaskTemplate(TaskTemplate):
    """快速任务模板 — 15 分钟即可完成的小事."""

    @property
    def name(self) -> str:
        return "quick"

    @property
    def description(self) -> str:
        return "快速任务（15 分钟内可完成）"

    def create(self, base_id: int, **overrides: Any) -> TemplateOutput:
        return TemplateOutput(tasks=[
            Task(
                id=base_id,
                title=overrides.get("title", "⚡ 快速任务"),
                priority=overrides.get("priority", 3),
                ddl=datetime.now() + timedelta(hours=2),
                tags=["快速"],
            ),
        ])


def get_builtin_templates() -> list[TaskTemplate]:
    """返回全部内置模板."""
    return [
        WeeklyReviewTemplate(),
        StudySessionTemplate(),
        QuickTaskTemplate(),
    ]
