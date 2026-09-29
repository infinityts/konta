"""Reportes: evolución mensual y desglose por categoría."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .jerarquia import mapa_etiquetas, ruta_etiqueta
from .models import Categoria, Etiqueta, Factura, FacturaLinea, TipoTransaccion, Transaccion
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
        .where(
            Transaccion.usuario_id == usuario_id,
            # Las transferencias entre cuentas propias no son ingreso ni gasto
            Transaccion.tipo != TipoTransaccion.TRANSFERENCIA,
        )
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
    """Desglose por categoría → etiqueta → subetiqueta para un mes (YYYY-MM)."""
    mapa_etq = mapa_etiquetas(db, usuario_id)
    filas = db.execute(
        select(
            Categoria,
            Etiqueta,
            Transaccion.tipo,
            func.sum(Transaccion.monto).label("total"),
        )
        .select_from(Transaccion)
        .join(Categoria, Categoria.id == Transaccion.categoria_id, isouter=True)
        .join(Etiqueta, Etiqueta.id == Transaccion.etiqueta_id, isouter=True)
        .where(
            Transaccion.usuario_id == usuario_id,
            func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
            # Sin categoría no hay desglose que mostrar
            Transaccion.tipo != TipoTransaccion.TRANSFERENCIA,
        )
        .group_by(Categoria.id, Etiqueta.id, Transaccion.tipo)
        .order_by(func.sum(Transaccion.monto).desc())
    ).all()
    return [
        {
            "categoria": categoria.nombre if categoria else "Sin categoría",
            "etiqueta": ruta_etiqueta(etiqueta, mapa_etq),
            "tipo": tipo.value,
            "total": float(total),
        }
        for categoria, etiqueta, tipo, total in filas
    ]


# --- panel de Reportes ------------------------------------------------------- #


def _mes_anterior(mes: str) -> str:
    y, m = int(mes[:4]), int(mes[5:7])
    m -= 1
    if m == 0:
        m, y = 12, y - 1
    return f"{y:04d}-{m:02d}"


def _fecha_compra():
    """Mes de una compra: la fecha de la factura, o la de su transacción si falta."""
    return func.to_char(func.coalesce(Factura.fecha_detectada, Transaccion.fecha), "YYYY-MM")


def panel(db: Session, usuario_id, meses: int = 12, mes: str | None = None) -> dict:
    """Todo lo que necesita la pestaña de Reportes, en una sola llamada.

    - `kpis`: ingresos, gastos, balance, IVA y compras del mes.
    - `serie`: últimos `meses` (ingresos, gastos, balance, IVA y compras por mes).
    - `categorias`: gasto por categoría del mes, con el mes anterior y la variación.
    - `mercado.etiquetas`: gasto por etiqueta del detalle de las facturas.
    - `mercado.productos`: top de artículos por gasto, veces y precio promedio.
    - `impuestos`: IVA del mes, del periodo y su peso sobre las compras.
    """
    mes = mes or hoy().strftime("%Y-%m")
    anterior = _mes_anterior(mes)

    def _resumen(mes_: str) -> dict[str, float]:
        filas = db.execute(
            select(Transaccion.tipo, func.sum(Transaccion.monto))
            .where(
                Transaccion.usuario_id == usuario_id,
                func.to_char(Transaccion.fecha, "YYYY-MM") == mes_,
                Transaccion.tipo != TipoTransaccion.TRANSFERENCIA,
            )
            .group_by(Transaccion.tipo)
        ).all()
        d = {"ingresos": 0.0, "gastos": 0.0}
        for tipo, total in filas:
            d["ingresos" if tipo.value == "ingreso" else "gastos"] = float(total)
        return d

    # IVA por mes: la fecha de la factura, o la de su transacción si falta
    mes_iva = _fecha_compra()
    filas_iva = db.execute(
        select(mes_iva, func.coalesce(func.sum(Factura.iva_valor), 0))
        .select_from(Factura)
        .join(Transaccion, Transaccion.id == Factura.transaccion_id, isouter=True)
        .where(Factura.usuario_id == usuario_id, Factura.iva_valor.is_not(None))
        .group_by(mes_iva)
    ).all()
    iva_por_mes: dict[str, float] = {m: float(v or 0) for m, v in filas_iva}

    # Compras (detalle de las facturas) por mes
    fecha_expr = _fecha_compra()
    filas_compras = db.execute(
        select(fecha_expr, func.coalesce(func.sum(FacturaLinea.valor_total), 0))
        .select_from(FacturaLinea)
        .join(Factura, Factura.id == FacturaLinea.factura_id)
        .join(Transaccion, Transaccion.id == Factura.transaccion_id, isouter=True)
        .where(Factura.usuario_id == usuario_id)
        .group_by(fecha_expr)
    ).all()
    compras_por_mes: dict[str, float] = {m: float(v or 0) for m, v in filas_compras}

    # Serie mensual
    serie = reporte_mensual(db, usuario_id, meses)
    for s in serie:
        s["iva"] = iva_por_mes.get(s["mes"], 0.0)
        s["compras"] = compras_por_mes.get(s["mes"], 0.0)

    # Gasto por categoría del mes y del anterior
    def _categorias(mes_: str) -> dict[str, float]:
        filas = db.execute(
            select(Categoria.nombre, func.sum(Transaccion.monto))
            .select_from(Transaccion)
            .join(Categoria, Categoria.id == Transaccion.categoria_id)
            .where(
                Transaccion.usuario_id == usuario_id,
                func.to_char(Transaccion.fecha, "YYYY-MM") == mes_,
                Transaccion.tipo == TipoTransaccion.GASTO,
            )
            .group_by(Categoria.nombre)
        ).all()
        return {nombre: float(total) for nombre, total in filas}

    cat_mes, cat_prev = _categorias(mes), _categorias(anterior)
    categorias = [
        {"categoria": n, "total": t, "anterior": cat_prev.get(n, 0.0), "variacion": round(t - cat_prev.get(n, 0.0), 2)}
        for n, t in sorted(cat_mes.items(), key=lambda x: -x[1])
    ]

    # Gasto por etiqueta del detalle de las facturas
    def _etiquetas(mes_: str) -> dict[str, float]:
        filas = db.execute(
            select(func.coalesce(Etiqueta.nombre, "Sin etiqueta"), func.sum(FacturaLinea.valor_total))
            .select_from(FacturaLinea)
            .join(Factura, Factura.id == FacturaLinea.factura_id)
            .join(Transaccion, Transaccion.id == Factura.transaccion_id, isouter=True)
            .join(Etiqueta, Etiqueta.id == FacturaLinea.etiqueta_id, isouter=True)
            .where(Factura.usuario_id == usuario_id, _fecha_compra() == mes_)
            .group_by(Etiqueta.nombre)
        ).all()
        return {nombre: float(total) for nombre, total in filas}

    etq_mes, etq_prev = _etiquetas(mes), _etiquetas(anterior)
    etiquetas = [
        {"etiqueta": n, "total": t, "anterior": etq_prev.get(n, 0.0), "variacion": round(t - etq_prev.get(n, 0.0), 2)}
        for n, t in sorted(etq_mes.items(), key=lambda x: -x[1])
    ]

    # Top artículos del mes
    filas_prod = db.execute(
        select(
            FacturaLinea.descripcion,
            func.sum(FacturaLinea.valor_total),
            func.count(FacturaLinea.id),
            func.avg(FacturaLinea.valor_unitario),
        )
        .select_from(FacturaLinea)
        .join(Factura, Factura.id == FacturaLinea.factura_id)
        .join(Transaccion, Transaccion.id == Factura.transaccion_id, isouter=True)
        .where(Factura.usuario_id == usuario_id, _fecha_compra() == mes)
        .group_by(FacturaLinea.descripcion)
        .order_by(func.sum(FacturaLinea.valor_total).desc())
        .limit(20)
    ).all()
    productos = [
        {"descripcion": d, "total": float(t), "veces": int(n), "precio_promedio": float(p) if p is not None else None}
        for d, t, n, p in filas_prod
    ]

    resumen_mes = _resumen(mes)
    iva_mes = iva_por_mes.get(mes, 0.0)
    compras_mes = compras_por_mes.get(mes, 0.0)
    return {
        "mes": mes,
        "anterior": anterior,
        "kpis": {
            "ingresos": resumen_mes["ingresos"],
            "gastos": resumen_mes["gastos"],
            "balance": round(resumen_mes["ingresos"] - resumen_mes["gastos"], 2),
            "iva": iva_mes,
            "compras": compras_mes,
        },
        "serie": serie,
        "categorias": categorias,
        "mercado": {"etiquetas": etiquetas, "productos": productos},
        "impuestos": {
            "mes": iva_mes,
            "periodo": round(sum(iva_por_mes.values()), 2),
            "sobre_compras": round(iva_mes / compras_mes * 100, 1) if compras_mes else None,
        },
    }
