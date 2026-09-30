"""Scheduler en segundo plano: ingresos recurrentes, cobros y notificaciones."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from .archivos import limpiar_archivos_vencidos, medir_almacenamiento_diario
from .notificaciones import procesar_notificaciones
from .pagos import limpiar_planes_vencidos
from .recurrencia import (
    procesar_ingresos_vencidos,
    procesar_polizas_vencidas,
    procesar_suscripciones_vencidas,
)
from .tasas import actualizar_trm_diaria

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
    # Las suscripciones generan su transacción de gasto al vencer
    _scheduler.add_job(
        procesar_suscripciones_vencidas,
        "interval",
        hours=1,
        id="suscripciones-vencidas",
        max_instances=1,
        coalesce=True,
    )
    # Las pólizas de seguro generan su gasto al vencer la prima
    _scheduler.add_job(
        procesar_polizas_vencidas,
        "interval",
        hours=1,
        id="polizas-vencidas",
        max_instances=1,
        coalesce=True,
    )
    # Los planes de pago vencen: se vuelve al plan base (00:10 en Colombia)
    _scheduler.add_job(
        limpiar_planes_vencidos,
        "cron",
        hour=5,
        minute=10,
        id="vencer-planes",
        max_instances=1,
        coalesce=True,
    )
    # El almacenamiento se mide una vez al día (23:50 en Colombia): cada día suma al mes lo que
    # ocupan los archivos, que es lo que permite cobrar el espacio con criterio.
    _scheduler.add_job(
        medir_almacenamiento_diario,
        "cron",
        hour=4,
        minute=50,
        id="medir-almacenamiento",
        max_instances=1,
        coalesce=True,
    )
    # Los archivos de las facturas se guardan con retención limitada: se limpia lo vencido
    _scheduler.add_job(
        limpiar_archivos_vencidos,
        "interval",
        hours=12,
        id="archivos-vencidos",
        max_instances=1,
        coalesce=True,
    )
    # La TRM oficial cambia todos los días hábiles: se trae cada 6 horas
    _scheduler.add_job(
        actualizar_trm_diaria,
        "interval",
        hours=6,
        id="trm-oficial",
        max_instances=1,
        coalesce=True,
    )
    # Revisa cada hora y envía como máximo un resumen al día (dedup por fecha)
    _scheduler.add_job(
        procesar_notificaciones,
        "interval",
        hours=1,
        id="notificaciones-pagos",
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
