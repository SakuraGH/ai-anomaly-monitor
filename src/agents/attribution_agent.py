"""归因 Agent：对异常事件执行多维下钻归因分析，生成报告。"""

from src.attribution.dimension_drill import drill_all_dimensions
from src.attribution.evidence_collector import EvidenceCollector
from src.attribution.multi_level_drill import multi_level_drill
from src.metrics.loader import MetricLoader
from src.metrics.registry import MetricRegistry
from src.models.anomaly_event import AnomalyEvent
from src.models.attribution_result import AttributionResult


class AttributionAgent:
    """归因 Agent —— 对异常事件执行完整归因分析。

    职责：
    - 多维度下钻计算贡献度
    - 多层递归下钻定位根因
    - 收集上下文证据
    - 生成分析摘要（通过 LLM Summarizer 或规则降级）
    """

    def __init__(
        self,
        registry: MetricRegistry,
        loader: MetricLoader,
        evidence_collector: EvidenceCollector | None = None,
        summarizer=None,
        top_n: int = 5,
        max_drill_depth: int = 3,
        baseline_window_weeks: int = 4,
    ):
        self.registry = registry
        self.loader = loader
        self.evidence_collector = evidence_collector or EvidenceCollector()
        self.summarizer = summarizer  # Summarizer 实例或 None（降级到规则）
        self.top_n = top_n
        self.max_drill_depth = max_drill_depth
        self.baseline_window_weeks = baseline_window_weeks

    def run(self, anomaly: AnomalyEvent) -> AttributionResult:
        """对单个异常事件执行完整的归因分析。"""
        metric = self.registry.get_metric(anomaly.metric_id)

        # 第一层：对所有维度计算贡献度
        first_levels = drill_all_dimensions(
            metric, anomaly.event_date, self.loader,
            top_n=self.top_n,
            baseline_window_weeks=self.baseline_window_weeks,
        )

        all_levels = list(first_levels)

        # 对贡献最大的维度继续多层下钻
        if first_levels:
            top_level = first_levels[0]
            deeper = multi_level_drill(
                metric, anomaly.event_date, self.loader,
                first_level=top_level,
                max_depth=self.max_drill_depth,
                top_n=self.top_n,
                baseline_window_weeks=self.baseline_window_weeks,
            )
            all_levels.extend(deeper)

        # 临时构建结果用于证据收集
        result = AttributionResult(
            metric_id=anomaly.metric_id,
            metric_name=anomaly.metric_name,
            event_date=anomaly.event_date,
            current_value=anomaly.current_value,
            baseline_value=anomaly.baseline_value,
            change_rate=anomaly.change_rate,
            drill_levels=all_levels,
        )

        # 收集证据
        evidence = self.evidence_collector.collect(anomaly, result)
        result.evidence = evidence

        # 生成摘要：优先使用 Summarizer（LLM 或规则降级），否则纯规则
        if self.summarizer is not None:
            result.summary = self.summarizer.summarize(anomaly, result, evidence)
        else:
            from src.llm.summarizer import build_rule_summary
            result.summary = build_rule_summary(anomaly, result)

        # 填充 top 贡献者
        for level in all_levels:
            if level.items:
                top = level.items[0]
                if abs(top.contribution_pct) > result.top_contribution_pct:
                    result.top_contributor = f"{top.dimension}={top.dimension_value}"
                    result.top_contribution_pct = abs(top.contribution_pct)

        return result
