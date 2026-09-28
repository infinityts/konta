"""Simulador de pago de deuda de tarjeta de crédito.

Modelo: interés compuesto **mensual**. La `tasa_interes` de la tarjeta se
interpreta como tasa mensual (convención común en Colombia, ej. 0.02 = 2%).
"""

from __future__ import annotations

from decimal import Decimal

MAX_MESES = 600
PAGO_MINIMO_PCT = Decimal("0.05")


def pago_minimo(saldo: Decimal) -> Decimal:
    """Pago mínimo sugerido: 5% del saldo."""
    return (saldo * PAGO_MINIMO_PCT).quantize(Decimal("0.01"))


def simular_pago(saldo: Decimal, tasa_mensual: Decimal, pago_mensual: Decimal) -> dict:
    """Simula mes a mes hasta pagar la deuda.

    `viable=False` cuando el pago no cubre los intereses del mes (la deuda
    nunca baja).
    """
    base = {
        "saldo_inicial": saldo,
        "tasa_mensual": tasa_mensual,
        "pago_mensual": pago_mensual,
    }

    if pago_mensual <= (saldo * tasa_mensual):
        return {**base, "meses": 0, "total_intereses": Decimal("0.00"), "total_pagado": Decimal("0.00"), "viable": False}

    saldo_actual = saldo
    total_intereses = Decimal("0.00")
    total_pagado = Decimal("0.00")
    meses = 0

    while saldo_actual > 0 and meses < MAX_MESES:
        interes = (saldo_actual * tasa_mensual).quantize(Decimal("0.01"))
        total_intereses += interes
        saldo_actual += interes
        pago = min(pago_mensual, saldo_actual)
        saldo_actual -= pago
        total_pagado += pago
        meses += 1

    return {
        **base,
        "meses": meses,
        "total_intereses": total_intereses.quantize(Decimal("0.01")),
        "total_pagado": total_pagado.quantize(Decimal("0.01")),
        "viable": saldo_actual <= 0,
    }
