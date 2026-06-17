"""多层下钻：对 top1 贡献维度值继续交叉其他维度拆分。"""

from datetime import date as date_type, timedelta

import pandas as pd

from src.metrics.loader import MetricLoader
from src.models.metric import MetricDefinition
from src.models.attribution_result import ContributionItem, DrillDownLevel


def _load_filtered_dimension_data(
    metric: MetricDefinition,
    target_date: date_type,
    loader: MetricLoader,
    cross_dimension: str,
    filters: dict[str, str],
    baseline_window_weeks: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载经过过滤条件筛选后的、按 cross_dimension 拆分的数据。

    返回 (current_df, baseline_df)，各含 cross_dimension 和 value 列。
    """
    source = loader._get_source(metric)
    cfg = loader._metric_config_dict(metric)

    # -- 加载当前日期的全量明细并过滤 --
    raw = source.query_metric_by_dimension(
        metric.metric_id, cross_dimension, target_date, target_date, cfg,
    )
    # raw 只有 date, cross_dimension, value，需要从原始数据再取
    # 改用直接从文件加载完整行再过滤
    from src.data_source.csv_source import CSVSource
    if not isinstance(source, CSVSource):
        # 非 CSV 数据源的简化处理：仅返回无过滤的结果
        baseline_frames = []
        for w in range(1, baseline_window_weeks + 1):
            ref = target_date - timedelta(weeks=w)
            df = source.query_metric_by_dimension(
                metric.metric_id, cross_dimension, ref, ref, cfg,
            )
            if not df.empty:
                baseline_frames.append(df)
        baseline = (
            pd.concat(baseline_frames).groupby(cross_dimension)["value"]
            .mean().reset_index() if baseline_frames
            else pd.DataFrame(columns=[cross_dimension, "value"])
        )
        return raw, baseline

    # CSV 数据源：从缓存获取原始 DataFrame 做精确过滤
    ds = metric.data_source
    full_df = source._load_file(ds.path)
    full_df = full_df.copy()
    full_df[ds.date_column] = pd.to_datetime(full_df[ds.date_column]).dt.date

    if "metric_id" in full_df.columns:
        full_df = full_df[full_df["metric_id"] == metric.metric_id]

    for dim_name, dim_value in filters.items():
        if dim_name in full_df.columns:
            full_df = full_df[full_df[dim_name] == dim_value]

    # 当前日期
    cur = full_df[full_df[ds.date_column] == target_date]
    current_agg = (
        cur.groupby(cross_dimension)[ds.value_column]
        .sum().reset_index()
        .rename(columns={ds.value_column: "value"})
    )

    # 基线期（近 N 周同一星期几）
    baseline_frames = []
    for w in range(1, baseline_window_weeks + 1):
        ref = target_date - timedelta(weeks=w)
        ref_data = full_df[full_df[ds.date_column] == ref]
        if not ref_data.empty:
            agg = (
                ref_data.groupby(cross_dimension)[ds.value_column]
                .sum().reset_index()
                .rename(columns={ds.value_column: "value"})
            )
            baseline_frames.append(agg)

    if baseline_frames:
        baseline_agg = (
            pd.concat(baseline_frames)
            .groupby(cross_dimension)["value"]
            .mean().reset_index()
        )
    else:
        baseline_agg = pd.DataFrame(columns=[cross_dimension, "value"])

    return current_agg, baseline_agg


def multi_level_drill(
    metric: MetricDefinition,
    target_date: date_type,
    loader: MetricLoader,
    first_level: DrillDownLevel,
    max_depth: int = 3,
    top_n: int = 5,
    baseline_window_weeks: int = 4,
) -> list[DrillDownLevel]:
    """从第一层下钻结果出发，对 top1 贡献维度值继续交叉其他维度下钻。

    返回所有下钻层级的列表（不含第一层）。
    """
    if not first_level.items:
        return []

    all_dimensions = metric.dimension_names
    results: list[DrillDownLevel] = []
    filters: dict[str, str] = dict(first_level.filter_context)

    top_item = first_level.items[0]
    filters[first_level.dimension] = top_item.dimension_value

    remaining_dims = [d for d in all_dimensions if d not in filters]

    for depth, cross_dim in enumerate(remaining_dims):
        if depth >= max_depth - 1:
            break

        current_df, baseline_df = _load_filtered_dimension_data(
            metric, target_date, loader, cross_dim,
            filters, baseline_window_weeks,
        )

        merged = pd.merge(
            current_df, baseline_df,
            on=cross_dim, how="outer", suffixes=("_current", "_baseline"),
        ).fillna(0)

        merged["change"] = merged["value_current"] - merged["value_baseline"]
        total_change = merged["change"].sum()

        items: list[ContributionItem] = []
        for _, row in merged.iterrows():
            change = row["change"]
            contribution = change / total_change if total_change != 0 else 0.0
            items.append(ContributionItem(
                dimension=cross_dim,
                dimension_value=str(row[cross_dim]),
                current_value=float(row["value_current"]),
                baseline_value=float(row["value_baseline"]),
                change_amount=float(change),
                contribution_pct=float(contribution),
            ))

        items.sort(key=lambda x: abs(x.contribution_pct), reverse=True)
        items = items[:top_n]

        level = DrillDownLevel(
            dimension=cross_dim,
            total_change=float(total_change),
            items=items,
            filter_context=dict(filters),
        )
        results.append(level)

        if items:
            filters[cross_dim] = items[0].dimension_value

    return results
