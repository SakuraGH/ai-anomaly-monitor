"""日历修正：节假日、促销活动识别与基线修正。"""

from datetime import date as date_type
from pathlib import Path

import pandas as pd


WEEKDAY_FACTORS: dict[int, float] = {
    0: 1.05,   # 周一
    1: 1.02,   # 周二
    2: 1.00,   # 周三
    3: 0.98,   # 周四
    4: 1.03,   # 周五
    5: 0.90,   # 周六
    6: 0.88,   # 周日
}


class CalendarManager:
    """活动日历管理器：节假日/促销识别 + 基线修正。"""

    def __init__(self, calendar_path: str | Path | None = None):
        self._events: pd.DataFrame = pd.DataFrame(
            columns=["date", "event_type", "event_name", "expected_impact"]
        )
        if calendar_path is not None:
            self.load(calendar_path)

    def load(self, calendar_path: str | Path) -> None:
        path = Path(calendar_path)
        if path.exists():
            self._events = pd.read_csv(path, encoding="utf-8-sig")
            self._events["date"] = pd.to_datetime(self._events["date"]).dt.date

    def get_event(self, d: date_type) -> dict | None:
        rows = self._events[self._events["date"] == d]
        if rows.empty:
            return None
        row = rows.iloc[0]
        return {
            "event_type": row["event_type"],
            "event_name": row["event_name"],
            "expected_impact": row["expected_impact"],
        }

    def is_holiday(self, d: date_type) -> bool:
        event = self.get_event(d)
        return event is not None and event["event_type"] == "holiday"

    def is_promotion(self, d: date_type) -> bool:
        event = self.get_event(d)
        return event is not None and event["event_type"] == "promotion"

    def is_special_day(self, d: date_type) -> bool:
        return self.get_event(d) is not None

    def is_weekend(self, d: date_type) -> bool:
        return d.weekday() >= 5

    def weekday_factor(self, d: date_type) -> float:
        return WEEKDAY_FACTORS.get(d.weekday(), 1.0)

    def adjust_baseline(
        self,
        baseline: float,
        target_date: date_type,
        baseline_date: date_type | None = None,
    ) -> float:
        """修正基线值，消除星期周期效应。

        如果 target_date 是周六但 baseline_date 是周三的均值，
        则将基线乘以 (周六因子/周三因子) 来修正。
        """
        target_factor = self.weekday_factor(target_date)

        if baseline_date is not None:
            base_factor = self.weekday_factor(baseline_date)
        else:
            base_factor = 1.0

        if base_factor == 0:
            return baseline

        return baseline * (target_factor / base_factor)
