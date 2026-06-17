"""定时调度：使用 APScheduler 实现定时触发编排器。"""

from collections.abc import Callable
from datetime import datetime as dt

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class TaskScheduler:
    """定时任务调度器。

    使用 APScheduler 在后台按 cron 表达式定时执行监控管道。
    """

    def __init__(self):
        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={"misfire_grace_time": 300, "coalesce": True},
        )
        self._jobs: dict[str, str] = {}

    def add_cron_job(
        self,
        job_id: str,
        func: Callable,
        cron_expr: str,
    ) -> None:
        """添加 cron 定时任务。

        cron_expr: 5 字段 cron 表达式 "minute hour day month weekday"
        例："0 9 * * *" = 每天 09:00
        """
        parts = cron_expr.split()
        if len(parts) != 5:
            raise ValueError(f"cron 表达式格式错误: {cron_expr}，需要 5 个字段")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
            timezone="Asia/Shanghai",
        )
        self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            name=job_id,
        )
        self._jobs[job_id] = cron_expr

    def add_interval_job(
        self,
        job_id: str,
        func: Callable,
        hours: int = 1,
    ) -> None:
        """添加间隔定时任务（每 N 小时）。"""
        self._scheduler.add_job(
            func,
            trigger="interval",
            hours=hours,
            id=job_id,
            replace_existing=True,
            name=job_id,
        )
        self._jobs[job_id] = f"every_{hours}h"

    def remove_job(self, job_id: str) -> None:
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass
        self._jobs.pop(job_id, None)

    def start(self) -> None:
        self._scheduler.start()

    def shutdown(self, wait: bool = True) -> None:
        try:
            self._scheduler.shutdown(wait=wait)
        except Exception:
            pass

    @property
    def jobs(self) -> dict[str, str]:
        return dict(self._jobs)

    @property
    def next_fire_times(self) -> dict[str, dt | None]:
        result = {}
        for job_id, _ in self._jobs.items():
            job = self._scheduler.get_job(job_id)
            if job and hasattr(job, "next_run_time"):
                result[job_id] = job.next_run_time
            else:
                result[job_id] = None
        return result


def create_monitor_scheduler(
    orchestrator,
    cron_expr: str = "0 9 * * *",
) -> TaskScheduler:
    """快捷创建监控调度器：每天在指定时间自动运行管道。"""
    scheduler = TaskScheduler()

    def _run():
        orchestrator.run_pipeline()

    scheduler.add_cron_job("daily_monitor", _run, cron_expr)
    return scheduler
