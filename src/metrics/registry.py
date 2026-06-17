from pathlib import Path
from typing import Any

import yaml

from src.models.metric import MetricDefinition


class MetricRegistry:
    """指标注册表：加载、查询、增删改指标口径定义。"""

    def __init__(self, config_path: str | Path | None = None):
        self._metrics: dict[str, MetricDefinition] = {}
        if config_path is not None:
            self.load_from_yaml(config_path)

    def load_from_yaml(self, config_path: str | Path) -> None:
        path = Path(config_path)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        for item in data.get("metrics", []):
            metric = MetricDefinition(**item)
            self._metrics[metric.metric_id] = metric

    def save_to_yaml(self, config_path: str | Path) -> None:
        items = [m.model_dump() for m in self._metrics.values()]
        path = Path(config_path)
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                {"metrics": items},
                f,
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            )

    def get_metric(self, metric_id: str) -> MetricDefinition:
        if metric_id not in self._metrics:
            raise KeyError(f"指标 '{metric_id}' 不存在")
        return self._metrics[metric_id]

    def list_metrics(self) -> list[MetricDefinition]:
        return list(self._metrics.values())

    def add_metric(self, metric: MetricDefinition) -> None:
        if metric.metric_id in self._metrics:
            raise ValueError(f"指标 '{metric.metric_id}' 已存在")
        self._metrics[metric.metric_id] = metric

    def update_metric(self, metric_id: str, updates: dict[str, Any]) -> MetricDefinition:
        existing = self.get_metric(metric_id)
        updated_data = existing.model_dump()
        updated_data.update(updates)
        updated = MetricDefinition(**updated_data)
        self._metrics[metric_id] = updated
        return updated

    def delete_metric(self, metric_id: str) -> None:
        if metric_id not in self._metrics:
            raise KeyError(f"指标 '{metric_id}' 不存在")
        del self._metrics[metric_id]

    def has_metric(self, metric_id: str) -> bool:
        return metric_id in self._metrics

    def __len__(self) -> int:
        return len(self._metrics)
