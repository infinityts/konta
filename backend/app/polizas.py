"""Lógica de negocio de las pólizas de seguro.

Vive aquí y no en el router porque la usan dos sitios: `/polizas` (la página de
Seguros) y `/reportes/seguros` (el reporte de costo anual). Mismo patrón que
`app/reportes.py` con `app/routers/reportes.py`.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import EstadoSuscripcion, Poliza
from .recurrencia import factor_mensual
from .tasas import convertir


def prima_mensual_cop(db: Session, poliza: Poliza) -> float | None:
    """Prima llevada a mes y a COP. `None` si no hay tasa para su moneda.

    Normalizar a mes es lo que permite comparar: una prima anual de 600.000 pesa
    50.000 al mes, y una semestral 100.000.
    """
    monto = Decimal(str(poliza.prima)) * factor_mensual(poliza.periodicidad)
    if poliza.moneda != "COP":
        convertido = convertir(db, poliza.moneda, "COP", monto)
        if convertido is None:
            return None  # sin tasa no se puede sumar con honestidad
        monto = convertido
    return float(monto.quantize(Decimal("0.01")))


def resumen(db: Session, usuario_id) -> dict:
    """Costo de los seguros activos: total, desglose por tipo y monedas sin tasa."""
    activas = db.scalars(
        select(Poliza).where(
            Poliza.usuario_id == usuario_id,
            Poliza.estado == EstadoSuscripcion.ACTIVA,
        )
    ).all()

    mensual = Decimal("0")
    acumulado_por_tipo: dict[str, dict] = {}
    sin_tasa: list[str] = []

    for pol in activas:
        valor = prima_mensual_cop(db, pol)
        if valor is None:
            if pol.moneda not in sin_tasa:
                sin_tasa.append(pol.moneda)
            continue
        mensual += Decimal(str(valor))
        fila = acumulado_por_tipo.setdefault(
            pol.tipo, {"tipo": pol.tipo, "polizas": 0, "mensual": Decimal("0")}
        )
        fila["polizas"] += 1
        fila["mensual"] += Decimal(str(valor))

    mensual = mensual.quantize(Decimal("0.01"))
    ordenados = sorted(acumulado_por_tipo.values(), key=lambda f: f["mensual"], reverse=True)
    return {
        "polizas_activas": len(activas),
        "prima_mensual_cop": float(mensual),
        "prima_anual_cop": float((mensual * 12).quantize(Decimal("0.01"))),
        "sin_tasa": sin_tasa,
        "por_tipo": [
            {
                "tipo": fila["tipo"],
                "polizas": fila["polizas"],
                "prima_mensual_cop": float(fila["mensual"].quantize(Decimal("0.01"))),
                "prima_anual_cop": float((fila["mensual"] * 12).quantize(Decimal("0.01"))),
            }
            for fila in ordenados
        ],
    }
