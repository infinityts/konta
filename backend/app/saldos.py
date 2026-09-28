"""Saldos por cuenta, consolidado mes a mes y diagnóstico del sobregiro."""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .jerarquia import etiqueta_completa, mapa_etiquetas
from .models import (
    Categoria,
    Cuenta,
    EstadoSuscripcion,
    Etiqueta,
    IngresoRecurrente,
    Suscripcion,
    TipoTransaccion,
    Transaccion,
)
from .recurrencia import hoy

CERO = Decimal("0.00")


def _sumar_mes(fecha: date, n: int) -> date:
    y = fecha.year + (fecha.month - 1 + n) // 12
    m = (fecha.month - 1 + n) % 12 + 1
    return date(y, m, min(fecha.day, calendar.monthrange(y, m)[1]))


def _meses_desde(inicio: date, n: int) -> list[str]:
    return [f"{(f := _sumar_mes(inicio, i)).year:04d}-{f.month:02d}" for i in range(n)]


def _neto(filas, signo_ingreso: bool = True) -> Decimal:
    """Suma filas (tipo, total) tratando ingresos como positivos y gastos negativos."""
    total = CERO
    for tipo, monto in filas:
        valor = Decimal(monto)
        if (tipo is not None and getattr(tipo, "value", tipo) == "ingreso") == signo_ingreso:
            total += valor
        else:
            total -= valor
    return total


def saldo_cuentas(db: Session, usuario_id) -> dict:
    """Saldo actual de cada cuenta y saldo total (incluye movimientos sin cuenta)."""
    cuentas = db.scalars(
        select(Cuenta).where(Cuenta.usuario_id == usuario_id).order_by(Cuenta.nombre)
    ).all()

    filas = db.execute(
        select(Transaccion.cuenta_id, Transaccion.tipo, func.sum(Transaccion.monto))
        .where(Transaccion.usuario_id == usuario_id, Transaccion.cuenta_id.is_not(None))
        .group_by(Transaccion.cuenta_id, Transaccion.tipo)
    ).all()
    mov: dict[tuple, Decimal] = {}
    for cuenta_id, tipo, total in filas:
        mov[(cuenta_id, tipo.value)] = Decimal(total)

    salida = []
    for c in cuentas:
        ingresos = mov.get((c.id, "ingreso"), CERO)
        gastos = mov.get((c.id, "gasto"), CERO)
        salida.append(
            {
                "id": c.id,
                "nombre": c.nombre,
                "tipo": c.tipo,
                "moneda": c.moneda,
                "activa": c.activa,
                "saldo_inicial": c.saldo_inicial,
                "ingresos": float(ingresos),
                "gastos": float(gastos),
                "saldo_actual": float(c.saldo_inicial + ingresos - gastos),
            }
        )

    sin_cuenta = _neto(
        db.execute(
            select(Transaccion.tipo, func.sum(Transaccion.monto))
            .where(Transaccion.usuario_id == usuario_id, Transaccion.cuenta_id.is_(None))
            .group_by(Transaccion.tipo)
        ).all()
    )
    sin_cuenta_n = (
        db.scalar(
            select(func.count())
            .select_from(Transaccion)
            .where(Transaccion.usuario_id == usuario_id, Transaccion.cuenta_id.is_(None))
        )
        or 0
    )

    total = sin_cuenta + sum(Decimal(str(c["saldo_actual"])) for c in salida)
    return {
        "saldo_total": float(total),
        "saldo_inicial_total": float(sum((c.saldo_inicial for c in cuentas), CERO)),
        "ingresos_total": float(sum((Decimal(str(c["ingresos"])) for c in salida), CERO)),
        "gastos_total": float(sum((Decimal(str(c["gastos"])) for c in salida), CERO)),
        "sin_cuenta": float(sin_cuenta),
        "sin_cuenta_movimientos": int(sin_cuenta_n),
        "sobregirado": total < 0,
        "cuentas": salida,
    }


def saldo_de_cuenta(db: Session, cuenta: Cuenta) -> dict:
    """Saldo de una sola cuenta (para las respuestas de crear/actualizar)."""
    filas = db.execute(
        select(Transaccion.tipo, func.sum(Transaccion.monto))
        .where(Transaccion.cuenta_id == cuenta.id)
        .group_by(Transaccion.tipo)
    ).all()
    ingresos = gastos = CERO
    for tipo, total in filas:
        if tipo.value == "ingreso":
            ingresos = Decimal(total)
        else:
            gastos = Decimal(total)
    return {
        "id": cuenta.id,
        "nombre": cuenta.nombre,
        "tipo": cuenta.tipo,
        "moneda": cuenta.moneda,
        "activa": cuenta.activa,
        "saldo_inicial": cuenta.saldo_inicial,
        "ingresos": float(ingresos),
        "gastos": float(gastos),
        "saldo_actual": float(cuenta.saldo_inicial + ingresos - gastos),
    }


def consolidado(db: Session, usuario_id, meses: int = 6) -> dict:
    """Mes a mes con saldo inicial, ingresos, gastos, balance y saldo final corrido."""
    hoy_ = hoy()
    primer_mes_actual = date(hoy_.year, hoy_.month, 1)
    inicio = _sumar_mes(primer_mes_actual, -(meses - 1))

    saldo_inicial_total = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(Cuenta.saldo_inicial), 0)).where(
                Cuenta.usuario_id == usuario_id
            )
        )
        or 0
    )
    saldo = saldo_inicial_total + _neto(
        db.execute(
            select(Transaccion.tipo, func.sum(Transaccion.monto))
            .where(Transaccion.usuario_id == usuario_id, Transaccion.fecha < inicio)
            .group_by(Transaccion.tipo)
        ).all()
    )

    mes_expr = func.to_char(Transaccion.fecha, "YYYY-MM")
    filas = db.execute(
        select(mes_expr, Transaccion.tipo, func.sum(Transaccion.monto))
        .where(Transaccion.usuario_id == usuario_id, Transaccion.fecha >= inicio)
        .group_by(mes_expr, Transaccion.tipo)
    ).all()
    por_mes: dict[str, dict[str, Decimal]] = {}
    for mes, tipo, total in filas:
        d = por_mes.setdefault(mes, {"ingresos": CERO, "gastos": CERO})
        d["ingresos" if tipo.value == "ingreso" else "gastos"] += Decimal(total)

    resultado = []
    for mes in _meses_desde(inicio, meses):
        d = por_mes.get(mes, {"ingresos": CERO, "gastos": CERO})
        inicial = saldo
        saldo = inicial + d["ingresos"] - d["gastos"]
        resultado.append(
            {
                "mes": mes,
                "saldo_inicial": float(inicial),
                "ingresos": float(d["ingresos"]),
                "gastos": float(d["gastos"]),
                "balance": float(d["ingresos"] - d["gastos"]),
                "saldo_final": float(saldo),
            }
        )
    return {"meses": resultado, "saldo_actual": float(saldo)}


def _totales_mes(db: Session, usuario_id, mes: str) -> tuple[Decimal, Decimal]:
    filas = db.execute(
        select(Transaccion.tipo, func.sum(Transaccion.monto))
        .where(
            Transaccion.usuario_id == usuario_id,
            func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
        )
        .group_by(Transaccion.tipo)
    ).all()
    ingresos = gastos = CERO
    for tipo, total in filas:
        if tipo.value == "ingreso":
            ingresos = Decimal(total)
        else:
            gastos = Decimal(total)
    return ingresos, gastos


def top_categorias(db: Session, usuario_id, mes: str, limite: int = 8) -> list[dict]:
    """Gastos del mes agrupados por categoría → etiqueta → subetiqueta."""
    mapa_etq = mapa_etiquetas(db, usuario_id)
    filas = db.execute(
        select(Categoria, Etiqueta, func.sum(Transaccion.monto))
        .select_from(Transaccion)
        .join(Categoria, Categoria.id == Transaccion.categoria_id, isouter=True)
        .join(Etiqueta, Etiqueta.id == Transaccion.etiqueta_id, isouter=True)
        .where(
            Transaccion.usuario_id == usuario_id,
            Transaccion.tipo == TipoTransaccion.GASTO,
            func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
        )
        .group_by(Categoria.id, Etiqueta.id)
        .order_by(func.sum(Transaccion.monto).desc())
        .limit(limite)
    ).all()

    return [
        {
            "tipo": "categoria",
            "etiqueta": etiqueta_completa(categoria, etiqueta, mapa_etq),
            "monto": float(total),
            "detalle": None,
        }
        for categoria, etiqueta, total in filas
    ]


def proximo_ingreso(db: Session, usuario_id) -> dict | None:
    """El ingreso recurrente activo más próximo (aún no generado)."""
    ing = db.scalar(
        select(IngresoRecurrente)
        .where(
            IngresoRecurrente.usuario_id == usuario_id,
            IngresoRecurrente.activa.is_(True),
        )
        .order_by(IngresoRecurrente.proxima_ejecucion)
        .limit(1)
    )
    if ing is None:
        return None
    return {"nombre": ing.nombre, "monto": float(ing.monto), "fecha": ing.proxima_ejecucion}


def diagnostico(db: Session, usuario_id) -> dict:
    """Estado del saldo y, si hay sobregiro, el motivo."""
    saldos = saldo_cuentas(db, usuario_id)
    saldo_actual = Decimal(str(saldos["saldo_total"]))

    hoy_ = hoy()
    mes_actual = f"{hoy_.year:04d}-{hoy_.month:02d}"
    mes_anterior = _sumar_mes(date(hoy_.year, hoy_.month, 1), -1).strftime("%Y-%m")

    ingresos, gastos = _totales_mes(db, usuario_id, mes_actual)
    ingresos_ant, gastos_ant = _totales_mes(db, usuario_id, mes_anterior)

    fijos = Decimal(
        db.scalar(
            select(func.coalesce(func.sum(Suscripcion.monto), 0)).where(
                Suscripcion.usuario_id == usuario_id,
                Suscripcion.estado == EstadoSuscripcion.ACTIVA,
            )
        )
        or 0
    )
    sin_cuenta_n = (
        db.scalar(
            select(func.count())
            .select_from(Transaccion)
            .where(Transaccion.usuario_id == usuario_id, Transaccion.cuenta_id.is_(None))
        )
        or 0
    )
    proximo = proximo_ingreso(db, usuario_id)
    tops = top_categorias(db, usuario_id, mes_actual)

    tiene_cuentas = bool(saldos["cuentas"])
    motivos: list[str] = []

    # 1) La causa raíz si no hay saldo inicial configurado
    if not tiene_cuentas:
        motivos.append(
            "No tienes cuentas configuradas: el saldo que ves es solo el flujo de tus "
            "movimientos, no tu dinero real."
        )
        motivos.append(
            "Crea una cuenta con el saldo que tienes hoy y el saldo pasará a ser real."
        )

    # 2) El estado del saldo
    if saldo_actual < 0:
        if tiene_cuentas:
            motivos.append(f"Tu saldo total está en {saldo_actual:,.2f}: estás sobregirado.")
        if gastos > ingresos:
            motivos.append(
                f"Este mes gastaste {gastos:,.2f} y entraron {ingresos:,.2f} "
                f"(déficit de {gastos - ingresos:,.2f})."
            )
        elif tiene_cuentas:
            motivos.append(
                f"Este mes el balance fue positivo ({ingresos - gastos:,.2f}); "
                "el sobregiro viene de meses anteriores."
            )
    else:
        motivos.append(f"Tu saldo total es {saldo_actual:,.2f}: estás al día.")
        if gastos > ingresos:
            motivos.append(
                f"Ojo: este mes vas con déficit de {gastos - ingresos:,.2f} "
                f"(gastos {gastos:,.2f} vs ingresos {ingresos:,.2f})."
            )

    # 3) Qué te está consumiendo
    if tops:
        primero = tops[0]
        motivos.append(
            f"Lo que más te consumió este mes fue {primero['etiqueta']} ({primero['monto']:,.2f})."
        )

    # 4) Gasto fijo
    if fijos > 0:
        motivos.append(f"Tus suscripciones activas suman {fijos:,.2f} al mes (gasto fijo).")

    # 5) Movimientos huérfanos
    if sin_cuenta_n and tiene_cuentas:
        motivos.append(
            f"{sin_cuenta_n} movimiento(s) sin cuenta asignada por "
            f"{abs(saldos['sin_cuenta']):,.2f}: asígnalos para que el saldo cuadre."
        )

    # 6) Ingreso recurrente que aún no llega
    if proximo is not None:
        dias = (proximo["fecha"] - hoy_).days
        if 0 <= dias <= 7:
            motivos.append(
                f"Tu ingreso «{proximo['nombre']}» de {proximo['monto']:,.2f} llega el "
                f"{proximo['fecha'].isoformat()} (en {dias} día(s)) y todavía no está sumado."
            )

    return {
        "saldo_actual": float(saldo_actual),
        "sobregirado": saldo_actual < 0,
        "tiene_cuentas": tiene_cuentas,
        "sin_cuenta_movimientos": int(sin_cuenta_n),
        "proximo_ingreso": proximo,
        "ingresos_mes": float(ingresos),
        "gastos_mes": float(gastos),
        "balance_mes": float(ingresos - gastos),
        "ingresos_mes_anterior": float(ingresos_ant),
        "gastos_mes_anterior": float(gastos_ant),
        "gastos_fijos": float(fijos),
        "motivos": motivos,
        "top_categorias": tops,
    }
