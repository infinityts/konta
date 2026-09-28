"""Lógica de recurrencia de ingresos.

Calcula la próxima ocurrencia según periodicidad y día, y genera las
transacciones de ingreso cuando corresponde (lo invoca el scheduler).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .config import get_settings
from .db import make_engine, make_session_factory
from .models import IngresoRecurrente, PeriodicidadIngreso, TipoTransaccion, Transaccion


def hoy() -> date:
    tz = ZoneInfo(get_settings().timezone)
    return datetime.now(tz).date()


def siguiente_ocurrencia(
    periodicidad: PeriodicidadIngreso, dia: int | None, desde: date
) -> date:
    if periodicidad == PeriodicidadIngreso.DIARIO:
        return desde + timedelta(days=1)
    if periodicidad == PeriodicidadIngreso.SEMANAL:
        return desde + timedelta(days=7)
    # mensual
    year, month = desde.year, desde.month + 1
    if month > 12:
        month, year = 1, year + 1
    ultimo = calendar.monthrange(year, month)[1]
    return date(year, month, min(dia or 1, ultimo))


def proxima_ocurrencia_inicial(
    periodicidad: PeriodicidadIngreso, dia: int | None
) -> date:
    hoy_ = hoy()
    if periodicidad == PeriodicidadIngreso.DIARIO:
        return hoy_
    if periodicidad == PeriodicidadIngreso.SEMANAL:
        delta = ((dia or 0) - hoy_.weekday()) % 7
        return hoy_ + timedelta(days=delta)
    # mensual
    ultimo_este_mes = calendar.monthrange(hoy_.year, hoy_.month)[1]
    if hoy_.day <= (dia or 1):
        return date(hoy_.year, hoy_.month, min(dia or 1, ultimo_este_mes))
    year, month = hoy_.year, hoy_.month + 1
    if month > 12:
        month, year = 1, year + 1
    ultimo = calendar.monthrange(year, month)[1]
    return date(year, month, min(dia or 1, ultimo))


def procesar_ingresos_vencidos() -> int:
    """Genera una transacción de ingreso por cada ingreso recurrente vencido.

    Devuelve el número de transacciones generadas. Es idempotente por periodo
    porque avanza `proxima_ejecucion` en cada ejecución.
    """
    engine = make_engine()
    sf = make_session_factory(engine)
    hoy_ = hoy()
    try:
        with sf.begin() as s:
            vencidos = s.scalars(
                select(IngresoRecurrente).where(
                    IngresoRecurrente.activa.is_(True),
                    IngresoRecurrente.proxima_ejecucion <= hoy_,
                )
            ).all()
            generados = 0
            for ing in vencidos:
                s.add(
                    Transaccion(
                        usuario_id=ing.usuario_id,
                        tipo=TipoTransaccion.INGRESO,
                        monto=ing.monto,
                        moneda=ing.moneda,
                        fecha=hoy_,
                        descripcion=ing.nombre,
                        categoria_id=ing.categoria_id,
                    )
                )
                ing.proxima_ejecucion = siguiente_ocurrencia(
                    ing.periodicidad, ing.dia, ing.proxima_ejecucion
                )
                generados += 1
        return generados
    finally:
        engine.dispose()
