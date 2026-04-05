"""调度层抽象接口 + 引力排序算法.

设计要点：
- Ranker / TaskBreaker / NextHopAdvisor 三个接口完全独立。
- 引力算法参数全部从配置注入，不硬编码权重。
- AI 相关接口留好 stub，具体实现在 Phase 3 填充。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow_engine.config import SchedulerConfig
    from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 抽象接口
# ---------------------------------------------------------------------------

class Ranker(ABC):
    """任务排序器合约."""

    @abstractmethod
    def rank(self, tasks: list[Task]) -> list[Task]:
        """返回按优先级排序的任务列表（最紧迫在前）."""


class TaskBreaker(ABC):
    """任务拆解器合约（AI 驱动）."""

    @abstractmethod
    def breakdown(self, task: Task) -> list[str]:
        """将一个大任务拆解为小步骤描述列表."""


class NextHopAdvisor(ABC):
    """下一跳推荐器合约."""

    @abstractmethod
    def suggest(self, tasks: list[Task], available_minutes: int) -> Task | None:
        """根据当前时间窗口推荐最适合立刻开始的任务."""


# ---------------------------------------------------------------------------
# 引力排序算法 — Ranker 的默认实现
# ---------------------------------------------------------------------------

class GravityRanker(Ranker):
    """基于多因子加权的引力排序算法.

    向后兼容包装器 — 内部委托给 CompositeRanker。
    新代码应直接使用 scheduler.factors.CompositeRanker。
    """

    def __init__(self, config: SchedulerConfig) -> None:
        from flow_engine.scheduler.factors import CompositeRanker, build_default_factors
        self._composite = CompositeRanker(
            factors=build_default_factors(
                priority_weight=config.priority_weight,
                ddl_weight=config.ddl_weight,
                dependency_weight=config.dependency_weight,
            ),
        )

    def rank(self, tasks: list[Task]) -> list[Task]:
        return self._composite.rank(tasks)


# ---------------------------------------------------------------------------
# Stub 实现 — 留好接口，Phase 3 填充
# ---------------------------------------------------------------------------

class StubBreaker(TaskBreaker):
    """占位拆解器 — 返回提示信息，待 AI 接入后替换."""

    def breakdown(self, task: Task) -> list[str]:
        return [f"[AI 未接入] 请手动拆解任务「{task.title}」"]


class StubAdvisor(NextHopAdvisor):
    """占位推荐器 — 返回引力排序的第一个任务."""

    def __init__(self, ranker: Ranker) -> None:
        self._ranker = ranker

    def suggest(self, tasks: list[Task], available_minutes: int) -> Task | None:
        ranked = self._ranker.rank(tasks)
        return ranked[0] if ranked else None
