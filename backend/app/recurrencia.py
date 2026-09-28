"""Lógica de recurrencia de ingresos.

Calcula la próxima ocurrencia según periodicidad y día, y genera las
transacciones de ingreso cuando corresponde (lo invoca el scheduler).
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import make_engine, make_session_factory
from .models import (
    EstadoSuscripcion,
    IngresoRecurrente,
    Periodicidad,
    PeriodicidadIngreso,
    Suscripcion,
    TipoTransaccion,
    Transaccion,
)


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


# --------------------------------------------------------------------------- #
# Suscripciones: generan su transacción de gasto al vencer
# --------------------------------------------------------------------------- #

MAX_CATCHUP = 24  # tope de periodos que se ponen al día en una sola pasada


def siguiente_pago(periodicidad: Periodicidad, desde: date) -> date:
    """Siguiente fecha de cobro de una suscripción."""
    if periodicidad == Periodicidad.SEMANAL:
        return desde + timedelta(days=7)

    meses = {
        Periodicidad.MENSUAL: 1,
        Periodicidad.TRIMESTRAL: 3,
        Periodicidad.ANUAL: 12,
    }.get(periodicidad, 1)

    year, month = desde.year, desde.month + meses
    while month > 12:
        month -= 12
        year += 1
    ultimo = calendar.monthrange(year, month)[1]
    return date(year, month, min(desde.day, ultimo))


def procesar_suscripciones(s: Session, hoy_: date) -> int:
    """Genera las transacciones de las suscripciones vencidas (lógica pura).

    Recibe la sesión y la fecha para poder probarla sin arrancar el scheduler.
    Devuelve cuántas transacciones generó.
    """
    vencidas = s.scalars(
        select(Suscripcion).where(
            Suscripcion.estado == EstadoSuscripcion.ACTIVA,
            Suscripcion.proximo_pago.is_not(None),
            Suscripcion.proximo_pago <= hoy_,
        )
    ).all()

    generadas = 0
    for sub in vencidas:
        periodos = 0
        while (
            sub.proximo_pago is not None
            and sub.proximo_pago <= hoy_
            and periodos < MAX_CATCHUP
        ):
            s.add(
                Transaccion(
                    usuario_id=sub.usuario_id,
                    tipo=TipoTransaccion.GASTO,
                    monto=sub.monto,
                    moneda=sub.moneda,
                    fecha=sub.proximo_pago,
                    descripcion=sub.nombre,
                    categoria_id=sub.categoria_id,
                    etiqueta_id=sub.etiqueta_id,
                    tarjeta_id=sub.tarjeta_id,
                    suscripcion_id=sub.id,
                )
            )
            sub.proximo_pago = siguiente_pago(sub.periodicidad, sub.proximo_pago)
            generadas += 1
            periodos += 1
    return generadas


def procesar_suscripciones_vencidas() -> int:
    """Envoltorio del scheduler: abre su propia sesión y aplica la lógica.

    La transacción hereda cuenta, categoría, etiqueta y tarjeta de la suscripción.
    Es idempotente: cada periodo procesado avanza `proximo_pago`.
    """
    engine = make_engine()
    sf = make_session_factory(engine)
    try:
        with sf.begin() as s:
            return procesar_suscripciones(s, hoy())
    finally:
        engine.dispose()
