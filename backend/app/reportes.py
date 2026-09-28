"""Reportes: evolución mensual y desglose por categoría."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Categoria, Transaccion
from .recurrencia import hoy


def _ultimos_meses(n: int) -> list[str]:
    hoy_ = hoy()
    meses: list[str] = []
    y, m = hoy_.year, hoy_.month
    for _ in range(n):
        meses.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return list(reversed(meses))


def reporte_mensual(db: Session, usuario_id, meses: int = 6) -> list[dict]:
    """Ingresos, gastos y balance por mes (últimos `meses`)."""
    mes_expr = func.to_char(Transaccion.fecha, "YYYY-MM")
    filas = db.execute(
        select(
            mes_expr.label("mes"),
            Transaccion.tipo,
            func.sum(Transaccion.monto).label("total"),
        )
        .where(Transaccion.usuario_id == usuario_id)
        .group_by(mes_expr, Transaccion.tipo)
    ).all()

    acumulado: dict[str, dict[str, float]] = {}
    for mes, tipo, total in filas:
        d = acumulado.setdefault(mes, {"ingresos": 0.0, "gastos": 0.0})
        d["ingresos" if tipo.value == "ingreso" else "gastos"] = float(total)

    resultado = []
    for m in _ultimos_meses(meses):
        d = acumulado.get(m, {"ingresos": 0.0, "gastos": 0.0})
        resultado.append(
            {
                "mes": m,
                "ingresos": d["ingresos"],
                "gastos": d["gastos"],
                "balance": round(d["ingresos"] - d["gastos"], 2),
            }
        )
    return resultado


def reporte_categorias(db: Session, usuario_id, mes: str) -> list[dict]:
    """Desglose por categoría para un mes (YYYY-MM)."""
    filas = db.execute(
        select(
            Categoria.nombre,
            Transaccion.tipo,
            func.sum(Transaccion.monto).label("total"),
        )
        .select_from(Transaccion)
        .join(Categoria, Categoria.id == Transaccion.categoria_id, isouter=True)
        .where(
            Transaccion.usuario_id == usuario_id,
            func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
        )
        .group_by(Categoria.nombre, Transaccion.tipo)
        .order_by(func.sum(Transaccion.monto).desc())
    ).all()
    return [
        {"categoria": nombre or "Sin categoría", "tipo": tipo.value, "total": float(total)}
        for nombre, tipo, total in filas
    ]
