"""Reportes: evolución mensual y desglose por categoría."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .jerarquia import mapa_categorias, ruta_categoria
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
    """Desglose por categoría → subcategoría para un mes (YYYY-MM)."""
    mapa = mapa_categorias(db, usuario_id)
    filas = db.execute(
        select(
            Categoria,
            Transaccion.tipo,
            func.sum(Transaccion.monto).label("total"),
        )
        .select_from(Transaccion)
        .join(Categoria, Categoria.id == Transaccion.categoria_id, isouter=True)
        .where(
            Transaccion.usuario_id == usuario_id,
            func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
        )
        .group_by(Categoria.id, Transaccion.tipo)
        .order_by(func.sum(Transaccion.monto).desc())
    ).all()
    salida = []
    for categoria, tipo, total in filas:
        raiz, sub = ruta_categoria(categoria, mapa)
        salida.append(
            {
                "categoria": raiz,
                "subcategoria": sub,
                "tipo": tipo.value,
                "total": float(total),
            }
        )
    return salida
