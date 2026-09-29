"""El extracto CMR (Falabella) en PDF: columnas, pago, compras internacionales y conciliación.

Estos son los arreglos que salieron del archivo real de calibración
(`.tools/tmp/extractos/cuenta.pdf`, fuera de los repos). Las piezas se construyen con
**fragmentos sintéticos** (x, y, texto) porque lo que se prueba es el parser por
coordenadas, que es justo lo que no tenía tests: por eso los bugs pasaron.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.extractos import (
    ExtractoCrudo,
    Fragmento,
    columnas_por_encabezado,
    conciliacion_ok,
    conciliar,
    movimientos_desde_filas,
)

# Las tres líneas del encabezado del CMR: «Cuota a» / «pagar» / «este mes» van partidas
# en tres renglones (y=1188, 1201, 1214) y en ese orden.
ENCABEZADO = [
    Fragmento(y=1188, x=537.5, texto="Tasa"),
    Fragmento(y=1188, x=604.5, texto="Cuota a"),
    Fragmento(y=1193, x=313.0, texto="Titular o"),
    Fragmento(y=1194, x=187.5, texto="Detalle de"),
    Fragmento(y=1194, x=391.0, texto="Valor del"),
    Fragmento(y=1194, x=475.5, texto="Número"),
    Fragmento(y=1194, x=706.5, texto="Valor"),
    Fragmento(y=1201, x=68.5, texto="Fecha"),
    Fragmento(y=1201, x=609.5, texto="pagar"),
    Fragmento(y=1207, x=183.5, texto="movimiento"),
    Fragmento(y=1207, x=384.0, texto="movimiento"),
    Fragmento(y=1207, x=471.5, texto="de cuotas"),
    Fragmento(y=1207, x=695.5, texto="pendiente"),
    Fragmento(y=1214, x=601.0, texto="este mes"),
]


def _columnas():
    resultado = columnas_por_encabezado(ENCABEZADO)
    assert resultado is not None
    y_encabezado, columnas, hacia_abajo = resultado
    return y_encabezado, columnas, hacia_abajo


def test_la_columna_de_la_cuota_del_mes_se_detecta_partida_en_tres_renglones():
    """Se une en orden de lectura: al revés quedaba `ESTEMESPAGARCUOTAA` y se perdía."""
    _, columnas, _ = _columnas()
    campos = {campo for campo, _ in columnas}
    assert "cuota_mes" in campos, columnas
    assert "valor_pendiente" in campos and "valor" in campos


def test_el_pago_va_en_la_columna_de_la_cuota_y_no_se_come_la_fila_siguiente():
    """El CMR dibuja el `-$612.126,00` del pago en la x de la cuota (592) y sin valor."""
    _, columnas, hacia_abajo = _columnas()
    filas = [
        Fragmento(y=2398, x=52.0, texto="03/07/2026"),
        Fragmento(y=2398, x=153.5, texto="PAG O TARJETA C MR"),
        Fragmento(y=2398, x=331.0, texto="TT"),
        Fragmento(y=2398, x=592.5, texto="-$ 6 12 .12 6 ,0 0"),
        # El `$86.090,03` de PAYPAL va en su propio renglón, 25 puntos arriba de su compra
        Fragmento(y=2423, x=394.0, texto="$86.090,03"),
        Fragmento(y=2434, x=52.0, texto="07/07/2026"),
        Fragmento(y=2434, x=132.5, texto="PAYPAL *INTERSERVER 7700 EA"),
        Fragmento(y=2434, x=331.0, texto="TT"),
        Fragmento(y=2434, x=408.0, texto="25,81"),
        Fragmento(y=2434, x=430.5, texto="US D"),
        Fragmento(y=2434, x=466.5, texto="1 de 1"),
        Fragmento(y=2434, x=516.0, texto="28,15%"),
        Fragmento(y=2434, x=605.5, texto="$ 86 .0 9 0 ,0 3"),
        Fragmento(y=2434, x=736.0, texto="$0,00"),
    ]
    movs = movimientos_desde_filas(filas, 1214.0, columnas, "COP", hacia_abajo)
    pago = next(m for m in movs if "PAG" in m.descripcion.replace(" ", ""))
    assert pago.tipo == "pago"
    assert pago.valor == Decimal("-612126.00")
    assert pago.cuota_mes is None, "el importe del pago no es una cuota"

    compra = next(m for m in movs if "PAYPAL" in m.descripcion)
    assert compra.valor == Decimal("86090.03"), "el peso va en su propio renglón"
    assert compra.monto_original == Decimal("25.81")
    assert compra.moneda_original == "USD"
    assert compra.cuota_mes == Decimal("86090.03")


def test_una_cuota_con_los_digitos_separados_se_arregla_con_la_aritmetica():
    """`$ 8.0 0 ,0 0` es `$8.000,00`: el extractor pierde un cero del grupo de miles."""
    _, columnas, hacia_abajo = _columnas()
    filas = [
        Fragmento(y=2362, x=51.5, texto="02/07/2026"),
        Fragmento(y=2362, x=129.0, texto="GOOGLE *PLAY YOUTUBE*D CR 7"),
        Fragmento(y=2362, x=400.0, texto="$8.000,00"),
        Fragmento(y=2362, x=466.5, texto="1 de 1"),
        Fragmento(y=2362, x=515.5, texto="28,76%"),
        Fragmento(y=2362, x=612.5, texto="$ 8.0 0 ,0 0"),
        Fragmento(y=2362, x=736.0, texto="$0,00"),
    ]
    movs = movimientos_desde_filas(filas, 1214.0, columnas, "COP", hacia_abajo)
    assert movs[0].cuota_mes == Decimal("8000.00"), "una compra de una cuota vale su valor"


def test_la_conciliacion_del_cmr_cuadra_con_el_capital_facturado():
    """«Consumos del mes facturados» es el **capital** facturado, no el valor de compras."""
    from app.extractos import MovimientoCrudo

    extracto = ExtractoCrudo(
        tipo="tarjeta",
        moneda="COP",
        banco="Falabella",
        periodo_desde=date(2026, 6, 30),
        periodo_hasta=date(2026, 7, 29),
        saldo_anterior=Decimal("2966499.76"),
        compras=Decimal("489088.85"),  # «consumos del mes facturados» = capital
        compras_periodo=Decimal("335018.95"),
        intereses=Decimal("46458.45"),
        otros_cargos=Decimal("31990.00"),
        seguro=Decimal("3990.00"),
        abonos=Decimal("612126.00"),
        pago_total=Decimal("2771831.16"),
        cupo_total=Decimal("5660000.00"),
        cupo_disponible=Decimal("2888168.84"),
        compras_es_capital=True,
    )
    # Tres compras pendientes: sus cuotas del mes suman el capital facturado
    for cuota in ("400000.00", "80000.00", "9088.85"):
        extracto.movimientos.append(
            MovimientoCrudo(
                fecha=date(2026, 7, 1),
                descripcion="COMPRA",
                valor=Decimal("100000.00"),
                cuota_mes=Decimal(cuota),
                cuotas_n=1,
                cuotas_total=1,
                valor_pendiente=Decimal("0.00"),
            ).cerrar()
        )
    extracto.movimientos.append(
        MovimientoCrudo(
            fecha=date(2026, 7, 3),
            descripcion="PAGO TARJETA CMR",
            valor=Decimal("-612126.00"),
        ).cerrar()
    )

    checks = conciliar(extracto)
    por_nombre = {c["nombre"]: c for c in checks}
    assert por_nombre["capital facturado del mes"]["ok"] is True, por_nombre["capital facturado del mes"]
    assert por_nombre["pagos y abonos"]["ok"] is True
    assert por_nombre["pago total"]["ok"] is True
    assert conciliacion_ok(checks) is True
