"""Metas de ahorro: progreso, restante y aporte mensual sugerido."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import AporteMeta, MetaAhorro
from .recurrencia import hoy


def _construir(meta: MetaAhorro, aportado: Decimal) -> dict:
    objetivo = float(meta.monto_objetivo)
    actual = float(aportado)
    restante = max(objetivo - actual, 0.0)
    porcentaje = round(actual / objetivo * 100, 1) if objetivo else 0.0

    sugerido = None
    if meta.fecha_limite is not None and restante > 0:
        dias = (meta.fecha_limite - hoy()).days
        if dias > 0:
            meses = max(dias / 30.0, 1.0)
            sugerido = round(restante / meses, 2)

    return {
        "id": meta.id,
        "nombre": meta.nombre,
        "monto_objetivo": meta.monto_objetivo,
        "moneda": meta.moneda,
        "monto_actual": round(actual, 2),
        "restante": round(restante, 2),
        "porcentaje": porcentaje,
        "fecha_limite": meta.fecha_limite,
        "aporte_mensual_sugerido": sugerido,
        "completada": actual >= objetivo > 0,
        "notas": meta.notas,
    }


def listar(db: Session, usuario_id) -> list[dict]:
    metas = db.scalars(
        select(MetaAhorro).where(MetaAhorro.usuario_id == usuario_id).order_by(MetaAhorro.creada_en)
    ).all()
    totales = dict(
        db.execute(
            select(AporteMeta.meta_id, func.sum(AporteMeta.monto))
            .where(AporteMeta.usuario_id == usuario_id)
            .group_by(AporteMeta.meta_id)
        ).all()
    )
    return [_construir(m, totales.get(m.id, Decimal("0"))) for m in metas]


def construir_una(db: Session, meta: MetaAhorro) -> dict:
    total = db.scalar(
        select(func.coalesce(func.sum(AporteMeta.monto), 0)).where(AporteMeta.meta_id == meta.id)
    )
    return _construir(meta, Decimal(total))
