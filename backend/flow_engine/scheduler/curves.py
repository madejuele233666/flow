"""迫切度曲线策略 — 将非线性数学公式与因子逻辑彻底解耦.

设计要点（用户核心诉求：解耦计算公式 + 优雅性）：
- UrgencyCurve 是纯粹的数学函数合约：输入 [0.0, 1.0] 归一化进度，输出 [0.0, 1.0] 迫切度。
- 因子（GravityFactor）只负责"如何将任务属性映射到进度值"。
- 曲线只负责"如何将进度值映射到迫切度分数"。
- 两者通过构造器注入组合（Strategy Pattern），完全正交。

丙方（用户/插件）可自由提供自定义曲线，无需修改任何因子代码。

曲线可视化：

    Linear:          Polynomial:       Exponential:
    1│      /         1│       /         1│        |
     │    /            │     /            │       /
     │  /              │   /              │     /
     │/                │ _/               │___/
    0└──────           0└──────           0└──────
     0      1           0      1           0      1
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod


class UrgencyCurve(ABC):
    """迫切度映射曲线 — 纯数学函数合约.

    合约：
    - 输入 progress ∈ [0.0, 1.0]，0 = 刚创建也好 / 距离 DDL 极远，1 = 已过期 / 极近。
    - 输出 score ∈ [0.0, 1.0]，0 = 不紧迫，1 = 极紧迫。
    - 必须是单调非递减函数（进度越大，迫切度不低于之前）。
    """

    @abstractmethod
    def __call__(self, progress: float) -> float:
        """将归一化进度映射为迫切度分数."""


# ---------------------------------------------------------------------------
# 内置曲线实现
# ---------------------------------------------------------------------------

class LinearCurve(UrgencyCurve):
    """线性曲线 — f(x) = x.

    最朴素的映射：进度等比例转换为迫切度。
    """

    def __call__(self, progress: float) -> float:
        return max(0.0, min(1.0, progress))


class PolynomialCurve(UrgencyCurve):
    """多项式曲线 — f(x) = x^n.

    指数 n > 1 时，前期增长缓慢、后期急剧上升（"温水煮青蛙"效果）。
    n = 2 为二次抛物线，n = 3 为三次曲线。

    Args:
        exponent: 多项式指数，默认 2.0（抛物线）。
    """

    def __init__(self, exponent: float = 2.0) -> None:
        self._exp = exponent

    def __call__(self, progress: float) -> float:
        p = max(0.0, min(1.0, progress))
        return p ** self._exp


class ExponentialCurve(UrgencyCurve):
    """指数曲线 — f(x) = (e^(kx) - 1) / (e^k - 1).

    在死线临近的最后时段，迫切度爆发式增长。
    k 越大，曲线越"陡峭"(临近 deadline 时越激进)。

    Args:
        steepness: 陡峭系数，默认 5.0（温和指数增长）。
    """

    def __init__(self, steepness: float = 5.0) -> None:
        self._k = steepness

    def __call__(self, progress: float) -> float:
        p = max(0.0, min(1.0, progress))
        return (math.exp(self._k * p) - 1.0) / (math.exp(self._k) - 1.0)


class StepCurve(UrgencyCurve):
    """阶梯曲线 — 在阈值处突然跳变.

    用于"临界值提醒"型场景：在某个进度阈值前迫切度为 0，超过后瞬间拉满。

    Args:
        threshold: 跳变进度阈值，默认 0.85（最后 15% 时间段触发）。
    """

    def __init__(self, threshold: float = 0.85) -> None:
        self._threshold = threshold

    def __call__(self, progress: float) -> float:
        return 1.0 if progress >= self._threshold else 0.0
