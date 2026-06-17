"""编排器：串联 监控 → 归因 → 存储 → 生成 Markdown 报告 全流程。"""

import logging
import uuid
from datetime import date as date_type, datetime as dt
from pathlib import Path
from typing import Callable

from src.agents.attribution_agent import AttributionAgent
from src.agents.monitor_agent import MonitorAgent
from src.models.anomaly_event import AnomalyEvent
from src.models.attribution_result import AttributionResult
from src.models.pipeline_result import PipelineResult

logger = logging.getLogger(__name__)

# Use absolute path relative to this file (ai-anomaly-monitor/reports/)
REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _build_markdown_report(
    anomaly: AnomalyEvent,
    attribution: AttributionResult,
) -> str:
    """从异常事件和归因结果生成 Markdown 报告文本。"""
    direction = "下降" if anomaly.change_rate < 0 else "上升"
    sev_map = {"high": "高", "medium": "中", "low": "低", "info": "信息"}

    lines = [
        f"# 异常分析报告",
        f"",
        f"**生成时间：** {dt.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## 异常摘要",
        f"",
        f"| 项目 | 值 |",
        f"|------|-----|",
        f"| 指标 | {anomaly.metric_name} |",
        f"| 日期 | {anomaly.event_date} |",
        f"| 当前值 | {anomaly.current_value:,.2f} |",
        f"| 基线值 | {anomaly.baseline_value:,.2f} |",
        f"| 变化率 | {anomaly.change_rate:.2%} |",
        f"| Z-score | {anomaly.z_score:.2f} |",
        f"| 严重级别 | {sev_map.get(anomaly.severity.value, anomaly.severity.value)} |",
        f"| 检测方法 | {', '.join(anomaly.detection_methods)} |",
        f"",
    ]

    if attribution.summary:
        lines.append(f"## AI 分析摘要")
        lines.append(f"")
        lines.append(attribution.summary)
        lines.append(f"")

    if attribution.drill_levels:
        lines.append(f"## 归因下钻")
        lines.append(f"")
        for i, lvl in enumerate(attribution.drill_levels):
            dim = lvl.dimension
            ctx = lvl.filter_context
            title = f"### 第{i + 1}层：按{dim}拆分"
            if ctx:
                ctx_desc = ", ".join(f"{k}={v}" for k, v in ctx.items())
                title += f" (筛选条件: {ctx_desc})"
            lines.append(title)
            lines.append(f"")
            lines.append(f"| 维度值 | 当前值 | 基线值 | 变化量 | 贡献占比 |")
            lines.append(f"|--------|--------|--------|--------|----------|")
            for item in lvl.items:
                lines.append(
                    f"| {item.dimension_value} "
                    f"| {item.current_value:,.2f} "
                    f"| {item.baseline_value:,.2f} "
                    f"| {item.change_amount:+,.2f} "
                    f"| {item.contribution_pct:.1%} |"
                )
            lines.append(f"")

    return "\n".join(lines)


class ResultStore:
    """管道执行结果的简单存储（后续可替换为数据库）。"""

    def __init__(self):
        self._results: list[PipelineResult] = []

    def save(self, result: PipelineResult) -> None:
        self._results.append(result)
        if len(self._results) > 100:
            self._results = self._results[-100:]

    def list(self, limit: int = 20) -> list[PipelineResult]:
        return self._results[-limit:]

    def get(self, run_id: str) -> PipelineResult | None:
        for r in self._results:
            if r.run_id == run_id:
                return r
        return None


class Orchestrator:
    """编排器：监控 Agent 检测 → 归因 Agent 分析 → AI 总结 → 存储结果。

    支持：
    - run_pipeline()      全量指标自动运行
    - run_single()        单个指标手动触发
    """

    def __init__(
        self,
        monitor: MonitorAgent,
        attributor: AttributionAgent,
        store: ResultStore | None = None,
        on_anomaly: Callable[[AnomalyEvent, AttributionResult], None] | None = None,
    ):
        self.monitor = monitor
        self.attributor = attributor
        self.store = store or ResultStore()
        self.on_anomaly = on_anomaly

    def _save_markdown_report(
        self,
        anomaly: AnomalyEvent,
        attribution: AttributionResult,
        run_id: str,
    ) -> str:
        """保存 Markdown 报告到 reports/ 目录。"""
        try:
            md = _build_markdown_report(anomaly, attribution)
            safe_metric = anomaly.metric_id.replace("/", "_").replace("\\", "_")
            safe_date = str(anomaly.event_date)
            filename = f"{safe_date}_{safe_metric}_{run_id}.md"
            filepath = REPORTS_DIR / filename
            filepath.write_text(md, encoding="utf-8")
            logger.info("Markdown 报告已保存: %s", filepath)
            return str(filepath)
        except Exception as e:
            logger.error("保存 Markdown 报告失败: %s", e)
            raise

    def run_pipeline(
        self,
        target_date: date_type | None = None,
    ) -> PipelineResult:
        """执行全量管道：对所有注册指标检测异常并归因。"""
        if target_date is None:
            target_date = date_type.today()

        run_id = uuid.uuid4().hex[:12]
        result = PipelineResult(
            run_id=run_id,
            run_time=dt.now(),
            target_date=target_date,
        )

        # 步骤1：监控 Agent 检测异常
        anomalies = self.monitor.run(target_date=target_date)
        result.anomalies = anomalies

        if not anomalies:
            result.message = f"{target_date} 未检测到异常"
            self.store.save(result)
            return result

        # 步骤2：对每个异常事件执行归因 Agent
        for anomaly in anomalies:
            try:
                attribution = self.attributor.run(anomaly)
                result.attributions[anomaly.metric_id] = attribution
                if self.on_anomaly:
                    self.on_anomaly(anomaly, attribution)
            except Exception:
                logger.exception("归因分析失败: %s", anomaly.metric_id)

            # 无论归因是否成功，尝试保存报告
            if anomaly.metric_id in result.attributions:
                try:
                    self._save_markdown_report(
                        anomaly, result.attributions[anomaly.metric_id], run_id,
                    )
                except Exception:
                    logger.exception("保存报告失败")

        result.message = (
            f"{target_date} 检测到 {len(anomalies)} 个异常，"
            f"完成 {len(result.attributions)} 个归因分析"
        )

        self.store.save(result)
        return result

    def run_single(
        self,
        metric_id: str,
        target_date: date_type | None = None,
    ) -> PipelineResult:
        """手动对单个指标执行全管道。"""
        if target_date is None:
            target_date = date_type.today()

        run_id = uuid.uuid4().hex[:12]
        result = PipelineResult(
            run_id=run_id,
            run_time=dt.now(),
            target_date=target_date,
        )

        anomalies = self.monitor.run([metric_id], target_date)
        result.anomalies = anomalies

        if anomalies:
            anomaly = anomalies[0]
            try:
                attribution = self.attributor.run(anomaly)
                result.attributions[anomaly.metric_id] = attribution
                if self.on_anomaly:
                    self.on_anomaly(anomaly, attribution)
            except Exception:
                logger.exception("归因分析失败: %s", anomaly.metric_id)

            # 无论归因是否成功，尝试保存报告
            if anomaly.metric_id in result.attributions:
                try:
                    self._save_markdown_report(
                        anomaly, result.attributions[anomaly.metric_id], run_id,
                    )
                except Exception:
                    logger.exception("保存报告失败")

        result.message = (
            f"{target_date} {metric_id} "
            f"{'检测到异常' if anomalies else '未检测到异常'}"
        )
        self.store.save(result)
        return result
