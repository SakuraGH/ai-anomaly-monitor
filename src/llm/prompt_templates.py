"""Prompt 模板：严格按视频中的输出规范设计，要求 AI 区分四类信息。"""

from src.models.anomaly_event import AnomalyEvent
from src.models.attribution_result import AttributionResult, EvidencePack


SYSTEM_PROMPT = """你是一个数据分析助手，负责基于**已计算的结构化证据**撰写异常分析报告。

## 重要约束
1. 你只能引用下方「证据」中列出的数据，不允许编造或猜测。
2. 必须严格区分四类信息：
   - 【已验证的事实】— 基于证据的确定性结论
   - 【可能的原因】— 候选假设
   - 【排查建议】— 下一步动作
   - 【需要补充的数据】— 还缺什么证据
3. 不要使用"可能"、"大概"等模糊词汇来描述已验证的事实。
4. 报告语言简洁专业，段落分明。"""


def build_anomaly_summary_prompt(
    anomaly: AnomalyEvent,
    result: AttributionResult,
    evidence: EvidencePack,
) -> tuple[str, str]:
    """构建异常摘要生成的 system + user prompt。

    返回 (system_prompt, user_message)
    """
    evidence_text = _format_evidence(evidence)

    user_message = f"""## 异常事件
- 指标：{anomaly.metric_name}
- 日期：{anomaly.event_date}
- 当前值：{anomaly.current_value:.0f}
- 基线值：{anomaly.baseline_value:.0f}
- 变化率：{anomaly.change_rate:+.1%}
- Z-score：{anomaly.z_score:.2f}
- 严重级别：{anomaly.severity.value}

## 证据
{evidence_text}

请基于以上证据生成分析报告，包含以下部分：
1. 【异常摘要】- 一句话描述异常情况
2. 【主要贡献来源】- 列出 Top 贡献因素及贡献占比
3. 【初步判断】- 区分已验证事实和可能原因
4. 【排查建议】- 具体的下一步行动
5. 【需要补充的数据】- 哪些证据还不够
"""

    return SYSTEM_PROMPT, user_message


def build_attribution_report_prompt(
    anomaly: AnomalyEvent,
    result: AttributionResult,
    evidence: EvidencePack,
) -> tuple[str, str]:
    """构建归因分析报告的 system + user prompt。"""
    evidence_text = _format_evidence(evidence)

    drill_text = ""
    for level in result.drill_levels:
        ctx = ""
        if level.filter_context:
            parts = [f"{k}={v}" for k, v in level.filter_context.items()]
            ctx = f"（过滤: {', '.join(parts)}）"
        drill_text += f"\n### {level.dimension} {ctx}\n"
        for item in level.items:
            drill_text += (
                f"- {item.dimension_value}: 当前{item.current_value:.0f} vs "
                f"基线{item.baseline_value:.0f}，变化{item.change_amount:+.0f}，"
                f"贡献{item.contribution_pct:.0%}\n"
            )

    user_message = f"""## 异常事件
{anomaly.message}

## 维度下钻结果
{drill_text}

## 上下文证据
{evidence_text}

请生成完整的归因分析报告。严格按照【已验证的事实】【可能的原因】【排查建议】
【需要补充的数据】四个部分组织，不允许编造未在证据中出现的数字。"""

    return SYSTEM_PROMPT, user_message


def build_investigation_suggestion_prompt(
    anomaly: AnomalyEvent,
    result: AttributionResult,
) -> tuple[str, str]:
    """构建排查建议生成的 system + user prompt。"""
    top_items = []
    for level in result.drill_levels:
        if level.items:
            top = level.items[0]
            top_items.append(
                f"{level.dimension}={top.dimension_value} "
                f"(贡献{top.contribution_pct:.0%})"
            )

    top_list = "\n".join(f"- {t}" for t in top_items)

    user_message = f"""## 异常概要
{anomaly.message}

## Top 贡献维度
{top_list}

请基于以上信息，生成 3-5 条具体的排查建议。每条建议需包含：
- 排查方向
- 预期发现的证据
- 排除或确认某类根因的方法
"""

    return SYSTEM_PROMPT, user_message


def _format_evidence(evidence: EvidencePack) -> str:
    parts = []
    for item in evidence.items:
        verified = "已验证" if item.verified else "待验证"
        parts.append(f"[{item.source}] [{verified}] {item.content}")
    return "\n".join(parts)
