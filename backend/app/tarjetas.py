"""Deuda de las tarjetas: el extracto es un **nivel**, los pagos un **flujo**.

La deuda de una tarjeta se registra como «lo que dice el extracto» (`DeudaTarjeta`),
y eso es un **nivel**: vale el último extracto de cada moneda. Antes se **sumaban**
todos, así que registrar el extracto de octubre además del de septiembre **contaba
la misma deuda dos veces**.

Los **pagos** (`PagoTarjeta`) son un **flujo**: se restan los posteriores a la fecha
del extracto vigente. Así el pago baja la deuda hoy, y cuando llegue el extracto
siguiente —que ya lo incluye— se convierte en el nuevo nivel y el pago deja de
restarse: no se cuenta dos veces al revés.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Cuenta, DeudaTarjeta, PagoTarjeta, Tarjeta
from .tasas import obtener_tasa

CERO = Decimal("0")


def extracto_vigente(db: Session, tarjeta: Tarjeta) -> dict[str, DeudaTarjeta]:
    """El extracto más reciente de cada moneda (el que manda como nivel)."""
    filas = db.scalars(
        select(DeudaTarjeta)
        .where(
            DeudaTarjeta.tarjeta_id == tarjeta.id,
            DeudaTarjeta.usuario_id == tarjeta.usuario_id,
        )
        .order_by(DeudaTarjeta.fecha.desc(), DeudaTarjeta.creada_en.desc())
    ).all()

    vigente: dict[str, DeudaTarjeta] = {}
    for d in filas:
        vigente.setdefault(d.moneda, d)  # el primero es el más reciente
    return vigente


def pagos_posteriores(
    db: Session, tarjeta: Tarjeta, extractos: dict[str, DeudaTarjeta]
) -> dict[str, Decimal]:
    """Pagos de cada moneda **después** del extracto vigente de esa moneda."""
    filas = db.scalars(
        select(PagoTarjeta)
        .where(
            PagoTarjeta.tarjeta_id == tarjeta.id,
            PagoTarjeta.usuario_id == tarjeta.usuario_id,
        )
        .order_by(PagoTarjeta.fecha)
    ).all()
    por_moneda: dict[str, Decimal] = {}
    for pago in filas:
        extracto = extractos.get(pago.moneda)
        # Un pago **anterior** al extracto ya viene incluido en él (el extracto es
        # posterior al pago): restarlo sería contarlo dos veces. Del mismo día en
        # adelante cuenta: lo normal es pagar después de recibir el extracto, y a
        # menudo el mismo día que lo registras.
        if extracto is not None and pago.fecha < extracto.fecha:
            continue
        por_moneda[pago.moneda] = por_moneda.get(pago.moneda, CERO) + Decimal(pago.monto)
    return por_moneda


def deuda_por_moneda(
    db: Session, tarjeta: Tarjeta
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """`(extracto, pagos, vigente)` por moneda.

    `vigente = extracto − pagos posteriores`. Es lo que se debe **hoy**.
    """
    extractos = extracto_vigente(db, tarjeta)
    pagos = pagos_posteriores(db, tarjeta, extractos)

    de_extracto = {m: float(d.monto) for m, d in extractos.items()}
    de_pagos = {m: float(v) for m, v in pagos.items()}
    monedas = set(de_extracto) | set(de_pagos)
    vigente = {
        m: round(de_extracto.get(m, 0.0) - de_pagos.get(m, 0.0), 2) for m in monedas
    }
    return de_extracto, de_pagos, vigente


def con_deuda(db: Session, tarjeta: Tarjeta) -> dict:
    """Tarjeta + deuda vigente por moneda + total en COP (si hay tasas)."""
    deudas = db.scalars(
        select(DeudaTarjeta)
        .where(
            DeudaTarjeta.tarjeta_id == tarjeta.id,
            DeudaTarjeta.usuario_id == tarjeta.usuario_id,
        )
        .order_by(DeudaTarjeta.fecha.desc())
    ).all()
    pagos = db.scalars(
        select(PagoTarjeta)
        .where(
            PagoTarjeta.tarjeta_id == tarjeta.id,
            PagoTarjeta.usuario_id == tarjeta.usuario_id,
        )
        .order_by(PagoTarjeta.fecha.desc())
    ).all()

    de_extracto, de_pagos, vigente = deuda_por_moneda(db, tarjeta)

    total_cop = 0.0
    completo = True
    for moneda, monto in vigente.items():
        if moneda == "COP":
            total_cop += monto
            continue
        tasa = obtener_tasa(db, moneda, "COP")
        if tasa is None:
            completo = False
            break
        total_cop += monto * float(tasa)

    nombre_cuenta = None
    if tarjeta.cuenta_id:
        cuenta = db.get(Cuenta, tarjeta.cuenta_id)
        nombre_cuenta = cuenta.nombre if cuenta else None

    return {
        "id": tarjeta.id,
        "usuario_id": tarjeta.usuario_id,
        "nombre": tarjeta.nombre,
        "banco": tarjeta.banco,
        "tipo": tarjeta.tipo,
        "moneda": tarjeta.moneda,
        "dia_corte": tarjeta.dia_corte,
        "dia_pago": tarjeta.dia_pago,
        "limite": tarjeta.limite,
        "tasa_interes": tarjeta.tasa_interes,
        "tasa_interes_ea": tarjeta.tasa_interes_ea,
        "cuenta_id": tarjeta.cuenta_id,
        "cuenta_nombre": nombre_cuenta,
        "activa": tarjeta.activa,
        "deudas": deudas,
        "pagos": pagos,
        # `deuda_por_moneda` es la **vigente** (extracto − pagos): es lo que se debe
        "deuda_por_moneda": vigente,
        "extracto_por_moneda": de_extracto,
        "pagos_por_moneda": de_pagos,
        "deuda_total_cop": round(total_cop, 2) if completo else None,
    }
