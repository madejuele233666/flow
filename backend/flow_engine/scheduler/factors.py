"""可插拔引力因子系统 + 组合式排序器.

设计来源:
- 原 GravityRanker 硬编码 3 因子, 重构为可插拔因子列表
- Phase 4: 因子与曲线完全解耦 (Strategy Pattern)
  - 因子负责 属性->进度值 的映射
  - 曲线负责 进度值->迫切度 的映射
  - 两者通过构造器注入组合, 完全正交

用法:
    from flow_engine.scheduler.curves import ExponentialCurve

    ranker = CompositeRanker()
    ranker.add_factor(PriorityFactor(weight=0.4))
    ranker.add_factor(DDLFactor(weight=0.4, curve=ExponentialCurve(steepness=8)))
    ranked = ranker.rank(tasks)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flow_engine.scheduler.curves import UrgencyCurve
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
    """DDL 紧迫度因子, 曲线可注入, 公式完全解耦.

    进度计算: remaining / horizon -> progress in [0.0, 1.0]
    迫切度映射: 由注入的 UrgencyCurve 决定 (默认 ExponentialCurve).

    Args:
        weight: 因子权重.
        curve: 迫切度映射曲线 (默认 ExponentialCurve(5.0), 死线前爆发增长).
        horizon_days: 预见窗口天数 (默认 7), 超出此范围的 DDL 进度为 0.
    """

    def __init__(
        self,
        weight: float = 1.0,
        curve: UrgencyCurve | None = None,
        horizon_days: float = 7.0,
    ) -> None:
        super().__init__(weight)
        from flow_engine.scheduler.curves import ExponentialCurve
        self._curve = curve or ExponentialCurve(steepness=5.0)
        self._horizon_seconds = horizon_days * 24 * 3600

    @property
    def name(self) -> str:
        return "ddl"

    def score(self, task: Task) -> float:
        if task.ddl is None:
            return 0.0
        remaining = (task.ddl - datetime.now()).total_seconds()
        if remaining <= 0:
            return 1.0
        progress = max(0.0, 1.0 - remaining / self._horizon_seconds)
        return self._curve(progress)


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
    """任务年龄因子, 曲线可注入, 公式完全解耦.

    进度计算: age / horizon -> progress in [0.0, 1.0]
    迫切度映射: 由注入的 UrgencyCurve 决定 (默认 PolynomialCurve(0.5) = sqrt(x)).

    Args:
        weight: 因子权重.
        curve: 迫切度映射曲线 (默认 PolynomialCurve(0.5), 早期增长快后期放缓).
        horizon_days: 老化窗口天数 (默认 7), 达到后得分封顶.
    """

    def __init__(
        self,
        weight: float = 1.0,
        curve: UrgencyCurve | None = None,
        horizon_days: float = 7.0,
    ) -> None:
        super().__init__(weight)
        from flow_engine.scheduler.curves import PolynomialCurve
        self._curve = curve or PolynomialCurve(exponent=0.5)
        self._horizon_seconds = horizon_days * 24 * 3600

    @property
    def name(self) -> str:
        return "age"

    def score(self, task: Task) -> float:
        age_seconds = (datetime.now() - task.created_at).total_seconds()
        progress = min(1.0, age_seconds / self._horizon_seconds)
        return self._curve(progress)


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
