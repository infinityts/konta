"""Parseo de dinero: los formatos que aparecen **de verdad** en extractos y facturas.

Estos casos salen de tres extractos reales (Davivienda, Amex y CMR) y del recibo de
prueba. No son inventados: cada uno rompió algo en algún momento.

| Antes (parser viejo) | Ahora |
|---|---|
| `44.900` → 44,9 | 44900 |
| `1.500.000` → `None` (fila descartada) | 1500000 |
| `44.900-` → 44,9 (perdía el signo) | -44900 |
| `$ 5.32 2 ,2 0` → error | 5322.20 |

Son tests puros (sin base de datos) para que corran siempre y rápido.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.dinero import (
    Formato,
    buscar_monto,
    buscar_montos,
    detectar_formato,
    parsear_monto,
    quitar_duplicado,
)


@pytest.mark.parametrize(
    ("texto", "formato", "esperado"),
    [
        # --- formato colombiano: el punto separa miles, la coma es decimal ---
        ("$5.195.786,83", Formato.CO, "5195786.83"),
        ("$ 353.076,89", Formato.CO, "353076.89"),
        ("$31.990,00", Formato.CO, "31990.00"),
        ("1.500.000", None, "1500000"),
        ("$2.771.831,16", Formato.CO, "2771831.16"),
        ("0,00", None, "0.00"),
        # --- ambiguos: los decide el formato del documento ---
        ("44.900", Formato.CO, "44900"),
        ("44.900", Formato.US, "44.900"),
        ("1,234", Formato.US, "1234"),
        ("1,234", Formato.CO, "1.234"),
        # --- estadounidense: la coma separa miles ---
        ("956,315.00", Formato.CO, "956315.00"),
        ("1,234.56", Formato.US, "1234.56"),
        # --- 1 o 2 decimales no son ambiguos ---
        ("8.00", None, "8.00"),
        ("135,00", None, "135.00"),
        ("10,54", None, "10.54"),
        # --- signos: delante, detrás y paréntesis ---
        ("-974.993,00", Formato.CO, "-974993.00"),
        ("$-1.103.790,03", Formato.CO, "-1103790.03"),
        ("-4,77", None, "-4.77"),
        ("44.900-", Formato.CO, "-44900"),
        ("(120.000)", Formato.CO, "-120000"),
        # --- lo que traen los PDF: espacios internos y valores duplicados ---
        ("$ 5.32 2 ,2 0", Formato.CO, "5322.20"),
        ("$9.568,71$9.568,71", Formato.CO, "9568.71"),
        ("9.568,719.568,71", Formato.CO, "9568.71"),
        ("$9.568,71 $9.568,71", Formato.CO, "9568.71"),
        # --- lo que NO es un monto ---
        ("45.000.00", Formato.CO, None),
        ("", None, None),
        ("   ", None, None),
        ("abc", None, None),
        ("EFECTIVO", None, None),
        ("$", None, None),
    ],
)
def test_parsear_monto(texto, formato, esperado):
    valor = parsear_monto(texto, formato)
    if esperado is None:
        assert valor is None, f"{texto!r} debería ser inválido y dio {valor}"
    else:
        assert valor == Decimal(esperado), f"{texto!r} -> {valor}, esperaba {esperado}"


def test_detectar_formato():
    """El formato del documento se infiere del conjunto de cifras."""
    # Extracto colombiano (Davivienda): todo con punto de miles y coma decimal
    assert (
        detectar_formato(["$5.195.786,83", "$ 353.076,89", "Cupo total: $5.000.000,00"])
        == Formato.CO
    )
    # Hoja de Amex en pesos: mayoría colombiana, con una cifra en formato US
    assert (
        detectar_formato(["9.424.224,90", "123.797,00", "956,315.00", "18.000.000,00"])
        == Formato.CO
    )
    # Documento estadounidense
    assert detectar_formato(["1,234.56", "Payment 135.00", "Balance 8.00"]) == Formato.US
    # Sin evidencia se asume el colombiano (es una app colombiana)
    assert detectar_formato(["1.234", "fecha 2026-09-05"]) == Formato.CO


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("US D US D", "US D"),
        ("T.C. T.C. $4.193,84", "T.C. $4.193,84"),
        ("$9.568,71$9.568,71", "$9.568,71"),
        ("$9.568,71 $9.568,71", "$9.568,71"),
        # No toca lo que no está repetido
        ("PAGOSEPAYCO TV 60", "PAGOSEPAYCO TV 60"),
        ("$ 5.32 2 ,2 0", "$ 5.32 2 ,2 0"),
    ],
)
def test_quitar_duplicado(texto, esperado):
    assert quitar_duplicado(texto) == esperado


def test_montos_de_los_extractos_reales():
    """Las cifras exactas de los tres extractos que se usaron para calibrar."""
    # PDF Davivienda: el desglose del pago total cuadra con estas cifras
    # Frases con etiqueta: se extrae el valor con `buscar_monto`
    saldo_anterior = buscar_monto("Saldo periodo anterior $5.197.599,35", Formato.CO)
    consumos = buscar_monto("+ Consumos del mes $1.004.353,02", Formato.CO)
    intereses = buscar_monto("+ Intereses corrientes $97.624,49", Formato.CO)
    pagos = buscar_monto("- Pagos (incluye abonos y cancelaciones) $-1.103.790,03", Formato.CO)
    assert saldo_anterior + consumos + intereses + pagos == Decimal("5195786.83")

    # XLSX Amex: compras + intereses + cuota de manejo − abonos = pago total
    saldo = parsear_monto("9.424.224,90", Formato.CO)
    compras = parsear_monto("123.797,00", Formato.CO)
    interes = parsear_monto("156.600,42", Formato.CO)
    cuota = parsear_monto("50.960,00", Formato.CO)
    abono = parsear_monto("974.993,00", Formato.CO)
    assert saldo + compras + interes + cuota - abono == Decimal("8780589.32")

    # CMR: pago mínimo y pago total
    assert (
        parsear_monto("$ 489.088,85", Formato.CO)
        + parsear_monto("$ 46.458,45", Formato.CO)
        + parsear_monto("$31.990,00", Formato.CO)
        + parsear_monto("$3.990,00", Formato.CO)
        == Decimal("571527.30")
    )
    assert parsear_monto("$2.771.831,16", Formato.CO) == Decimal("2771831.16")


def test_buscar_montos_en_lineas_de_extracto():
    """Una línea de extracto trae la etiqueta y los valores juntos."""
    assert buscar_montos("+ Intereses corrientes $97.624,49", Formato.CO) == [
        Decimal("97624.49")
    ]
    assert buscar_monto("Cupo total: $5.660.000,00", Formato.CO) == Decimal("5660000.00")

    # Los valores limpios de una fila se extraen todos, en orden
    fila = "$1.189.999,00 19 de 36 24,86% $33.055,53 $561.944,02"
    assert buscar_montos(fila, Formato.CO) == [
        Decimal("1189999.00"), Decimal("19"), Decimal("36"), Decimal("24.86"),
        Decimal("33055.53"), Decimal("561944.02"),
    ]

    # LÍMITE CONOCIDO: cuando el PDF pega dos valores sin separador
    # (`$108.515,3125,87` son pesos + dólares), el texto ya no se puede partir sin
    # adivinar. Por eso la Fase 1 parsea ese archivo **por columnas** (cada valor en
    # su `x`), no por expresiones regulares. Este test documenta que aquí no se
    # inventa un valor: el token queda cortado antes de la parte pegada.
    pegados = buscar_montos("$108.515,3125,87 US D 22 de 24", Formato.CO)
    assert pegados[0] < Decimal("108515.32"), "no se inventa un valor a partir del pegado"
