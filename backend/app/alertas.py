"""Cálculo de alertas de pagos próximos.

Genera avisos a partir de:
- suscripciones activas con `proximo_pago`
- tarjetas activas con `dia_pago` o `dia_corte`
"""

from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EstadoSuscripcion, Suscripcion, Tarjeta
from .recurrencia import hoy


def proxima_fecha_dia_mes(dia: int) -> date:
    """Próxima ocurrencia del día `dia` (1-31) a partir de hoy."""
    hoy_ = hoy()
    ultimo = calendar.monthrange(hoy_.year, hoy_.month)[1]
    if hoy_.day <= dia:
        return date(hoy_.year, hoy_.month, min(dia, ultimo))
    year, month = hoy_.year, hoy_.month + 1
    if month > 12:
        month, year = 1, year + 1
    ultimo = calendar.monthrange(year, month)[1]
    return date(year, month, min(dia, ultimo))


def calcular_alertas(db: Session, usuario_id, dias: int = 15) -> list[dict]:
    """Devuelve las alertas de pago dentro de los próximos `dias`."""
    hoy_ = hoy()
    alertas: list[dict] = []

    suscripciones = db.scalars(
        select(Suscripcion).where(
            Suscripcion.usuario_id == usuario_id,
            Suscripcion.estado == EstadoSuscripcion.ACTIVA,
            Suscripcion.proximo_pago.is_not(None),
        )
    ).all()
    for s in suscripciones:
        dr = (s.proximo_pago - hoy_).days
        if dr <= dias:
            alertas.append(
                {
                    "tipo": "suscripcion",
                    "titulo": s.nombre,
                    "fecha": s.proximo_pago,
                    "dias_restantes": dr,
                    "monto": s.monto,
                    "moneda": s.moneda,
                }
            )

    tarjetas = db.scalars(
        select(Tarjeta).where(Tarjeta.usuario_id == usuario_id, Tarjeta.activa.is_(True))
    ).all()
    for t in tarjetas:
        if t.dia_pago:
            f = proxima_fecha_dia_mes(t.dia_pago)
            dr = (f - hoy_).days
            if dr <= dias:
                alertas.append(
                    {
                        "tipo": "tarjeta_pago",
                        "titulo": f"Pago tarjeta {t.nombre}",
                        "fecha": f,
                        "dias_restantes": dr,
                        "monto": None,
                        "moneda": t.moneda,
                    }
                )
        if t.dia_corte:
            f = proxima_fecha_dia_mes(t.dia_corte)
            dr = (f - hoy_).days
            if dr <= dias:
                alertas.append(
                    {
                        "tipo": "tarjeta_corte",
                        "titulo": f"Corte tarjeta {t.nombre}",
                        "fecha": f,
                        "dias_restantes": dr,
                        "monto": None,
                        "moneda": t.moneda,
                    }
                )

    alertas.sort(key=lambda a: a["fecha"])
    return alertas
