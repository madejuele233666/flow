"""可插拔引力因子系统 + 组合式排序器.

设计来源：
- 原 GravityRanker 硬编码 3 因子 → 重构为可插拔因子列表
- 用户可通过配置调整权重，通过插件添加新因子

用法：
    ranker = CompositeRanker()
    ranker.add_factor(PriorityFactor(weight=0.4))
    ranker.add_factor(DDLFactor(weight=0.4))
    ranker.add_factor(MyCustomFactor(weight=0.2))
    ranked = ranker.rank(tasks)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow_engine.storage.task_model import Task

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 因子抽象
# ---------------------------------------------------------------------------

class GravityFactor(ABC):
    """引力排序因子合约.

    每个因子独立计算某一维度的分数 [0.0, 1.0]，
    由 CompositeRanker 加权求和。
    """

    def __init__(self, weight: float = 1.0) -> None:
        self._weight = weight

    @property
    @abstractmethod
    def name(self) -> str:
        """因子标识名."""

    @property
    def weight(self) -> float:
        """因子权重（可在配置中覆盖）."""
        return self._weight

    @weight.setter
    def weight(self, value: float) -> None:
        self._weight = value

    @abstractmethod
    def score(self, task: Task) -> float:
        """计算分数 [0.0, 1.0]，越高越紧迫."""


# ---------------------------------------------------------------------------
# 内置因子
# ---------------------------------------------------------------------------

class PriorityFactor(GravityFactor):
    """优先级因子 — P0=1.0, P1=0.75, P2=0.5, P3=0.25."""

    @property
    def name(self) -> str:
        return "priority"

    def score(self, task: Task) -> float:
        return max(0.0, 1.0 - task.priority * 0.25)


class DDLFactor(GravityFactor):
    """DDL 紧迫度因子 — 距离越近分越高."""

    @property
    def name(self) -> str:
        return "ddl"

    def score(self, task: Task) -> float:
        if task.ddl is None:
            return 0.0
        remaining = (task.ddl - datetime.now()).total_seconds()
        if remaining <= 0:
            return 1.0
        seven_days = 7 * 24 * 3600
        return max(0.0, 1.0 - remaining / seven_days)


class TagBoostFactor(GravityFactor):
    """标签加权因子 — 包含指定标签时加分.

    用法：
        TagBoostFactor(boost_tags=["urgent", "紧急"], weight=0.2)
    """

    def __init__(self, weight: float = 0.2, boost_tags: list[str] | None = None) -> None:
        super().__init__(weight)
        self._tags = set(boost_tags or ["urgent", "紧急"])

    @property
    def name(self) -> str:
        return "tag_boost"

    def score(self, task: Task) -> float:
        return 1.0 if self._tags & set(task.tags) else 0.0


class AgeFactor(GravityFactor):
    """任务年龄因子 — 创建越久未完成的任务分越高."""

    @property
    def name(self) -> str:
        return "age"

    def score(self, task: Task) -> float:
        age_seconds = (datetime.now() - task.created_at).total_seconds()
        seven_days = 7 * 24 * 3600
        return min(1.0, age_seconds / seven_days)


# ---------------------------------------------------------------------------
# 组合式排序器
# ---------------------------------------------------------------------------

class CompositeRanker:
    """可插拔因子的组合式排序器.

    替代原 GravityRanker，支持运行时增减因子。
    """

    def __init__(self, factors: list[GravityFactor] | None = None) -> None:
        self._factors: list[GravityFactor] = factors or []

    def add_factor(self, factor: GravityFactor) -> None:
        """添加一个排序因子."""
        self._factors.append(factor)
        logger.debug("ranker factor added: %s (w=%.2f)", factor.name, factor.weight)

    def remove_factor(self, name: str) -> None:
        """按名称移除因子."""
        self._factors = [f for f in self._factors if f.name != name]

    def list_factors(self) -> list[tuple[str, float]]:
        """返回 (name, weight) 列表."""
        return [(f.name, f.weight) for f in self._factors]

    def rank(self, tasks: list[Task]) -> list[Task]:
        """按加权分数排序（最紧迫在前）."""
        active_tasks = [t for t in tasks if not t.is_terminal]
        if not self._factors:
            return active_tasks

        scored = [(t, self._composite_score(t)) for t in active_tasks]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [t for t, _ in scored]

    def _composite_score(self, task: Task) -> float:
        total_weight = sum(f.weight for f in self._factors)
        if total_weight == 0:
            return 0.0
        raw = sum(f.weight * f.score(task) for f in self._factors)
        return raw / total_weight  # 归一化


def build_default_factors(
    priority_weight: float = 0.4,
    ddl_weight: float = 0.4,
    dependency_weight: float = 0.2,
) -> list[GravityFactor]:
    """构建默认因子列表（从配置参数）."""
    return [
        PriorityFactor(weight=priority_weight),
        DDLFactor(weight=ddl_weight),
        # dependency_weight 预留给未来的依赖因子
    ]
