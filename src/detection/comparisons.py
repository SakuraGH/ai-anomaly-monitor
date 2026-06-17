"""基础对比检测：同比、环比、移动平均。"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ComparisonResult:
    current: float
    baseline: float
    change_rate: float
    is_anomaly: bool
    method: str


def year_over_year(
    current: float,
    historical: float,
    threshold: float = 0.10,
) -> ComparisonResult:
    """同比检测：当前值 vs 去年同期值。"""
    if historical == 0:
        change_rate = 0.0 if current == 0 else float("inf")
    else:
        change_rate = (current - historical) / abs(historical)

    return ComparisonResult(
        current=current,
        baseline=historical,
        change_rate=change_rate,
        is_anomaly=abs(change_rate) > threshold,
        method="year_over_year",
    )


def month_over_month(
    current: float,
    previous: float,
    threshold: float = 0.10,
) -> ComparisonResult:
    """环比检测：当前值 vs 上一期值。"""
    if previous == 0:
        change_rate = 0.0 if current == 0 else float("inf")
    else:
        change_rate = (current - previous) / abs(previous)

    return ComparisonResult(
        current=current,
        baseline=previous,
        change_rate=change_rate,
        is_anomaly=abs(change_rate) > threshold,
        method="month_over_month",
    )


def moving_average(
    series: pd.Series | list[float],
    current: float | None = None,
    window: int = 7,
    threshold: float = 0.10,
) -> ComparisonResult:
    """移动平均检测：当前值 vs 近 N 期移动平均。

    如果 current 为 None，则取 series 最后一个值作为当前值，
    用前面的值计算移动平均作为基线。
    """
    if isinstance(series, list):
        series = pd.Series(series)

    if current is None:
        current = float(series.iloc[-1])
        history = series.iloc[:-1]
    else:
        history = series

    if len(history) == 0:
        return ComparisonResult(
            current=current, baseline=current,
            change_rate=0.0, is_anomaly=False, method="moving_average",
        )

    tail = history.tail(window)
    baseline = float(np.mean(tail))

    if baseline == 0:
        change_rate = 0.0 if current == 0 else float("inf")
    else:
        change_rate = (current - baseline) / abs(baseline)

    return ComparisonResult(
        current=current,
        baseline=baseline,
        change_rate=change_rate,
        is_anomaly=abs(change_rate) > threshold,
        method="moving_average",
    )


def baseline_compare(
    current: float,
    baseline_values: list[float] | pd.Series,
    threshold: float = 0.10,
) -> ComparisonResult:
    """基线均值对比：当前值 vs 基线期均值（如近4周同期均值）。"""
    if isinstance(baseline_values, pd.Series):
        baseline_values = baseline_values.tolist()

    if not baseline_values:
        return ComparisonResult(
            current=current, baseline=current,
            change_rate=0.0, is_anomaly=False, method="baseline_compare",
        )

    baseline = float(np.mean(baseline_values))

    if baseline == 0:
        change_rate = 0.0 if current == 0 else float("inf")
    else:
        change_rate = (current - baseline) / abs(baseline)

    return ComparisonResult(
        current=current,
        baseline=baseline,
        change_rate=change_rate,
        is_anomaly=abs(change_rate) > threshold,
        method="baseline_compare",
    )
