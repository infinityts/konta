"""Scheduler en segundo plano para ingresos recurrentes."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .recurrencia import procesar_ingresos_vencidos

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_job(
        procesar_ingresos_vencidos,
        "interval",
        hours=1,
        id="ingresos-recurrentes",
        max_instances=1,
        coalesce=True,
    )
    _scheduler.start()
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
