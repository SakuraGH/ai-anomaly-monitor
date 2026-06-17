"""统计检测：Z-score 和 3σ 检测。"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


PRIORITY_THRESHOLDS: dict[str, float] = {
    "P0": 2.0,
    "P1": 2.5,
    "P2": 3.0,
}


@dataclass
class ZScoreResult:
    current: float
    mean: float
    std: float
    z_score: float
    threshold: float
    is_anomaly: bool
    method: str


def z_score_detect(
    current: float,
    history_series: list[float] | pd.Series,
    threshold: float | None = None,
    priority: str = "P1",
) -> ZScoreResult:
    """Z-score 检测：判断当前值是否显著偏离历史分布。

    threshold 优先级：显式传入 > 按 priority 查表 > 默认 2.5
    """
    if isinstance(history_series, pd.Series):
        history_series = history_series.tolist()

    if len(history_series) < 2:
        return ZScoreResult(
            current=current, mean=current, std=0.0,
            z_score=0.0, threshold=2.5, is_anomaly=False,
            method="z_score",
        )

    mean = float(np.mean(history_series))
    std = float(np.std(history_series, ddof=1))

    if threshold is None:
        threshold = PRIORITY_THRESHOLDS.get(priority, 2.5)

    if std == 0:
        z = 0.0 if current == mean else float("inf")
    else:
        z = (current - mean) / std

    return ZScoreResult(
        current=current,
        mean=mean,
        std=std,
        z_score=z,
        threshold=threshold,
        is_anomaly=abs(z) > threshold,
        method="z_score",
    )


def three_sigma_detect(
    current: float,
    history_series: list[float] | pd.Series,
    sigma_multiplier: float | None = None,
    priority: str = "P1",
) -> ZScoreResult:
    """3σ 检测：判断当前值是否超出 mean ± N*σ 范围。

    sigma_multiplier 优先级：显式传入 > 按 priority 查表 > 默认 3.0
    """
    if isinstance(history_series, pd.Series):
        history_series = history_series.tolist()

    if sigma_multiplier is None:
        sigma_multiplier = PRIORITY_THRESHOLDS.get(priority, 3.0)

    result = z_score_detect(
        current, history_series,
        threshold=sigma_multiplier, priority=priority,
    )
    result.method = "three_sigma"
    return result
