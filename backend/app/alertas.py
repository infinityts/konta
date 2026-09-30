"""Cálculo de alertas de pagos próximos.

Genera avisos a partir de:
- suscripciones activas con `proximo_pago`
- pólizas de seguro activas: la prima (`proximo_pago`) y el fin de vigencia
  (`fecha_fin`, para avisar de la renovación)
- tarjetas activas con `dia_pago` o `dia_corte`
- el **extracto** de una tarjeta: si ya se leyó, la obligación de pago es el **pago
  total** con la **fecha límite que dice el propio extracto**, no una fecha estimada a
  partir del día de pago configurado.
"""

from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EstadoSuscripcion, Extracto, Poliza, Suscripcion, Tarjeta, Usuario
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

    polizas = db.scalars(
        select(Poliza).where(
            Poliza.usuario_id == usuario_id,
            Poliza.estado == EstadoSuscripcion.ACTIVA,
        )
    ).all()
    for p in polizas:
        if p.proximo_pago is not None:
            dr = (p.proximo_pago - hoy_).days
            if dr <= dias:
                alertas.append(
                    {
                        "tipo": "poliza_pago",
                        "titulo": f"Prima {p.titulo}",
                        "fecha": p.proximo_pago,
                        "dias_restantes": dr,
                        "monto": p.prima,
                        "moneda": p.moneda,
                    }
                )
        if p.fecha_fin is not None and not p.renovacion_automatica:
            dr = (p.fecha_fin - hoy_).days
            if dr <= dias:
                alertas.append(
                    {
                        "tipo": "poliza_vencimiento",
                        "titulo": f"Vence la póliza {p.titulo}",
                        "fecha": p.fecha_fin,
                        "dias_restantes": dr,
                        "monto": None,
                        "moneda": p.moneda,
                    }
                )

    tarjetas = db.scalars(
        select(Tarjeta).where(Tarjeta.usuario_id == usuario_id, Tarjeta.activa.is_(True))
    ).all()
    for t in tarjetas:
        # Si hay un extracto leído con fecha límite de pago, esa manda: es el dato real
        # (el pago total del corte), no una estimación por el día de pago configurado
        extracto = db.scalars(
            select(Extracto)
            .where(
                Extracto.tarjeta_id == t.id,
                Extracto.fecha_pago.is_not(None),
                Extracto.pago_total.is_not(None),
            )
            .order_by(Extracto.fecha_corte.desc().nullslast(), Extracto.creado_en.desc())
        ).first()
        if extracto is not None and extracto.fecha_pago is not None:
            dr = (extracto.fecha_pago - hoy_).days
            if dr <= dias:
                alertas.append(
                    {
                        "tipo": "tarjeta_pago",
                        "titulo": f"Pago tarjeta {t.nombre} (extracto del corte)",
                        "fecha": extracto.fecha_pago,
                        "dias_restantes": dr,
                        "monto": extracto.pago_total,
                        "moneda": extracto.moneda,
                        "origen": "extracto",
                    }
                )
        elif t.dia_pago:
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
    # El plan de pago: avisar antes de que venza (si no, el cliente se entera al perderlo)
    usuario = db.get(Usuario, usuario_id)
    if usuario is not None and usuario.plan_hasta is not None:
        from .pagos import estado_del_plan

        estado = estado_del_plan(usuario)
        dias_plan = estado["dias"] if estado["dias"] is not None else 0
        if dias_plan <= dias:
            alertas.append(
                {
                    "tipo": "plan_por_vencer",
                    "titulo": f"Tu plan {usuario.plan_codigo} vence el {usuario.plan_hasta}",
                    "fecha": usuario.plan_hasta,
                    "dias_restantes": dias_plan,
                    "descripcion": (
                        "Renuévalo desde Planes y lecturas para no volver al plan base."
                        if dias_plan >= 0
                        else "El plan ya venció: vuelve al plan base hasta que lo renueves."
                    ),
                }
            )

    return alertas
