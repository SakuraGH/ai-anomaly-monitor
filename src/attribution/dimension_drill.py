"""单维度贡献度计算。"""

from datetime import date as date_type

import pandas as pd

from src.metrics.loader import MetricLoader
from src.models.metric import MetricDefinition
from src.models.attribution_result import ContributionItem, DrillDownLevel


def drill_by_dimension(
    metric: MetricDefinition,
    dimension: str,
    target_date: date_type,
    loader: MetricLoader,
    top_n: int = 5,
    baseline_window_weeks: int = 4,
    filter_context: dict[str, str] | None = None,
) -> DrillDownLevel:
    """对单个维度计算每个维度值的贡献度。

    贡献度公式：贡献占比 = (当前维度值 - 基线维度值) / 总变化量
    """
    current_df = loader.load_current_by_dimension(metric, dimension, target_date)
    baseline_df = loader.load_baseline_by_dimension(
        metric, dimension, target_date, window_weeks=baseline_window_weeks,
    )

    merged = pd.merge(
        current_df, baseline_df,
        on=dimension, how="outer", suffixes=("_current", "_baseline"),
    ).fillna(0)

    merged["change"] = merged["value_current"] - merged["value_baseline"]
    total_change = merged["change"].sum()

    items: list[ContributionItem] = []
    for _, row in merged.iterrows():
        change = row["change"]
        if total_change != 0:
            contribution = change / total_change
        else:
            contribution = 0.0

        items.append(ContributionItem(
            dimension=dimension,
            dimension_value=str(row[dimension]),
            current_value=float(row["value_current"]),
            baseline_value=float(row["value_baseline"]),
            change_amount=float(change),
            contribution_pct=float(contribution),
        ))

    items.sort(key=lambda x: abs(x.contribution_pct), reverse=True)
    items = items[:top_n]

    return DrillDownLevel(
        dimension=dimension,
        total_change=float(total_change),
        items=items,
        filter_context=filter_context or {},
    )


def drill_all_dimensions(
    metric: MetricDefinition,
    target_date: date_type,
    loader: MetricLoader,
    top_n: int = 5,
    baseline_window_weeks: int = 4,
) -> list[DrillDownLevel]:
    """对指标的所有维度分别计算贡献度。"""
    results = []
    for dim_name in metric.dimension_names:
        level = drill_by_dimension(
            metric, dim_name, target_date, loader,
            top_n=top_n, baseline_window_weeks=baseline_window_weeks,
        )
        results.append(level)
    return results
