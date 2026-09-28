"""Presupuestos por categoría: límite mensual vs gasto real del mes."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Categoria, Presupuesto, TipoTransaccion, Transaccion
from .recurrencia import hoy


def _construir(db: Session, usuario_id, presupuestos: list[Presupuesto], mes: str) -> list[dict]:
    gastos = {
        cat_id: float(total)
        for cat_id, total in db.execute(
            select(Transaccion.categoria_id, func.sum(Transaccion.monto))
            .where(
                Transaccion.usuario_id == usuario_id,
                Transaccion.tipo == TipoTransaccion.GASTO,
                func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
            )
            .group_by(Transaccion.categoria_id)
        ).all()
    }
    nombres = {
        c.id: c.nombre
        for c in db.scalars(select(Categoria).where(Categoria.usuario_id == usuario_id)).all()
    }

    resultado = []
    for p in presupuestos:
        gastado = gastos.get(p.categoria_id, 0.0)
        limite = float(p.monto_limite)
        resultado.append(
            {
                "id": p.id,
                "categoria_id": p.categoria_id,
                "categoria_nombre": nombres.get(p.categoria_id, "—"),
                "monto_limite": p.monto_limite,
                "moneda": p.moneda,
                "gastado": round(gastado, 2),
                "restante": round(limite - gastado, 2),
                "porcentaje": round((gastado / limite * 100) if limite else 0.0, 1),
                "activo": p.activo,
            }
        )
    resultado.sort(key=lambda x: x["porcentaje"], reverse=True)
    return resultado


def listar_con_gasto(db: Session, usuario_id, mes: str | None = None) -> list[dict]:
    mes = mes or hoy().strftime("%Y-%m")
    presupuestos = db.scalars(
        select(Presupuesto).where(Presupuesto.usuario_id == usuario_id)
    ).all()
    return _construir(db, usuario_id, list(presupuestos), mes)


def construir_uno(db: Session, usuario_id, presupuesto: Presupuesto) -> dict:
    return _construir(db, usuario_id, [presupuesto], hoy().strftime("%Y-%m"))[0]
