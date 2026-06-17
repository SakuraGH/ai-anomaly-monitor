"""报告生成器：基于结构化证据调用 LLM 生成报告，防止幻觉。

同时保留规则摘要作为 LLM 不可用时的降级方案。
"""

import logging

from src.models.anomaly_event import AnomalyEvent
from src.models.attribution_result import AttributionResult, EvidencePack

from .base import LLMBase
from .prompt_templates import (
    build_anomaly_summary_prompt,
    build_attribution_report_prompt,
    build_investigation_suggestion_prompt,
)

logger = logging.getLogger(__name__)


def build_rule_summary(anomaly: AnomalyEvent, result: AttributionResult) -> str:
    """规则摘要（LLM 不可用时的降级方案），复用视频中的输出模板。"""
    top_level = result.drill_levels[0] if result.drill_levels else None
    top_item = top_level.items[0] if top_level and top_level.items else None

    lines = ["【异常摘要】"]
    direction = "下降" if anomaly.change_rate < 0 else "上升"
    lines.append(
        f"{anomaly.event_date} {anomaly.metric_name}为{anomaly.current_value:.0f}，"
        f"较基线{anomaly.baseline_value:.0f}{direction}{abs(anomaly.change_rate):.1%}，"
        f"判定为{anomaly.severity.value}优先级异常。"
    )

    if top_level and top_level.items:
        lines.append("")
        lines.append("【主要贡献来源】")
        for item in top_level.items:
            if abs(item.contribution_pct) < 0.05:
                continue
            d = "减少" if item.change_amount < 0 else "增加"
            lines.append(
                f"- {item.dimension_value}: {d} {abs(item.change_amount):.0f}，"
                f"贡献占比 {item.contribution_pct:.0%}"
            )

    if top_item:
        lines.append("")
        lines.append("【初步判断】")
        lines.append("【已验证的事实】")
        lines.append(
            f"  {top_item.dimension_value}的数据"
            f"{'下降' if top_item.change_amount < 0 else '上升'}了"
            f"{abs(top_item.change_rate):.0%}，"
            f"是{anomaly.metric_name}变化的主要原因。"
        )
        lines.append("【可能的原因】")
        lines.append(f"  1. {top_item.dimension_value}相关的供给或投放变化")
        lines.append("  2. 外部因素（竞品/政策/系统故障）")
        lines.append("【排查建议】")
        lines.append(f"  1. 核对{top_item.dimension_value}的状态和资源变化")
        lines.append("  2. 检查是否有外部因素影响")
        lines.append(f"  3. 若恢复后{anomaly.metric_name}同步恢复，记录为案例")
        lines.append("【需要补充的数据】")
        lines.append("  1. 具体的投放预算或流量供给变化记录")
        lines.append("  2. 同期竞品或行业动态信息")

    return "\n".join(lines)


class Summarizer:
    """报告生成器：调用 LLM 生成结构化的分析报告。

    设计原则（视频核心观点）：
    - 只给 LLM 结构化证据，不给原始全量数据
    - Prompt 中要求区分"已验证事实"和"可能原因"
    - LLM 不可用时降级到规则摘要
    """

    def __init__(self, llm: LLMBase | None = None):
        self.llm = llm

    def summarize(
        self,
        anomaly: AnomalyEvent,
        result: AttributionResult,
        evidence: EvidencePack | None = None,
    ) -> str:
        """生成异常分析报告。

        优先使用 LLM，不可用时降级到规则摘要。
        """
        ev = evidence or result.evidence or EvidencePack(
            metric_id=anomaly.metric_id,
            metric_name=anomaly.metric_name,
            event_date=anomaly.event_date,
            current_value=anomaly.current_value,
            baseline_value=anomaly.baseline_value,
            change_rate=anomaly.change_rate,
        )

        if self.llm is not None:
            try:
                system, user = build_attribution_report_prompt(
                    anomaly, result, ev,
                )
                return self.llm.generate_with_retry(system, user)
            except Exception as e:
                logger.warning("LLM 生成失败，降级到规则摘要: %s", e)

        return build_rule_summary(anomaly, result)

    def summarize_investigation(
        self,
        anomaly: AnomalyEvent,
        result: AttributionResult,
    ) -> str:
        """仅生成排查建议。"""
        if self.llm is not None:
            try:
                system, user = build_investigation_suggestion_prompt(
                    anomaly, result,
                )
                return self.llm.generate_with_retry(system, user)
            except Exception as e:
                logger.warning("LLM 排查建议生成失败: %s", e)

        # 降级
        return "请人工分析排查方向。"
