from abc import ABC, abstractmethod
from datetime import date
from typing import Any

import pandas as pd


class DataSource(ABC):
    """数据源抽象基类，定义所有数据源适配器的统一接口。"""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    def query_metric(
        self,
        metric_id: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """查询指标的每日汇总数据。

        返回 DataFrame 包含列: date, value
        """

    @abstractmethod
    def query_metric_by_dimension(
        self,
        metric_id: str,
        dimension: str,
        start_date: date,
        end_date: date,
        metric_config: dict[str, Any] | None = None,
    ) -> pd.DataFrame:
        """查询指标按某个维度拆分的每日数据。

        返回 DataFrame 包含列: date, {dimension}, value
        """

    @abstractmethod
    def test_connection(self) -> bool:
        """测试数据源连接是否正常。"""
