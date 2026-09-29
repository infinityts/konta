"""Motor de lectura de extractos: piezas puras y un Excel de punta a punta.

Los casos salen de los tres extractos reales que se usaron para calibrar (Davivienda y
CMR en PDF, Amex en Excel). Los archivos reales no se versionan: el Excel de prueba se
**construye** aquí con la misma estructura (dos tablas, cuotas, pago en positivo) y sin
ningún dato personal.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest

from app.extractos import (
    ExtractoCrudo,
    MovimientoCrudo,
    _cuotas_de,
    _fechas_con_anio_inferido,
    conciliacion_ok,
    conciliar,
    leer_excel,
    marcar_informativos,
    parsear,
    tipo_de_movimiento,
)


@pytest.mark.parametrize(
    ("descripcion", "valor", "cuotas", "esperado"),
    [
        # El caso que fallaba: "PAGOSEPAYCO" lleva PAGO dentro, pero no es un pago
        ("MOVISTAR PAGOSEPAYCO TV 60", Decimal("229649"), 24, "compra"),
        ("PAGO TARJETA CMR", Decimal("612126"), None, "pago"),
        ("PAGOS POR PSE", Decimal("-331137.01"), None, "pago"),
        ("ABONO SUCURSAL VIRTUAL", Decimal("-974993"), None, "pago"),
        ("INTERESES CORRIENTES", Decimal("156600.42"), None, "interes"),
        ("CUOTA DE MANEJO", Decimal("50960"), None, "comision"),
        ("COBRO SEGURO VIDA DEUDOR", Decimal("3990"), None, "comision"),
        ("IMPUESTO 4X1000 GMF", Decimal("1200"), None, "impuesto"),
        ("AJUSTE COMPRA PAGO MIN ALTERNO", Decimal("772653.02"), 24, "ajuste"),
        ("NOMINA SEPTIEMBRE", Decimal("4500000"), None, "nomina"),
        ("DLO*NETFLIX.COM", Decimal("44900"), 1, "compra"),
        ("RAPPI", Decimal("121900"), 24, "compra"),
    ],
)
def test_tipo_de_movimiento(descripcion, valor, cuotas, esperado):
    assert tipo_de_movimiento(descripcion, valor, cuotas) == esperado


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("7 de 24", (7, 24)),
        ("24 de 24", (24, 24)),
        ("1 de 1", (1, 1)),
        # La tasa viene pegada: `1 de 128,15%` es `1 de 1` + `28,15%`
        ("1 de 128,15%", (1, 1)),
        ("sin cuotas", None),
        ("0 de 0", None),
    ],
)
def test_cuotas_de(texto, esperado):
    assert _cuotas_de(texto) == esperado


def test_fechas_con_anio_inferido():
    """El Amex escribe `17 ago` sin año y `15 sep. 2026` con año."""
    fechas = _fechas_con_anio_inferido("PERIODO FACTURADO 17 AGO 15 SEP. 2026")
    assert fechas[:2] == [date(2026, 8, 17), date(2026, 9, 15)]


def test_conciliar_detecta_lo_que_no_cuadra():
    """Componentes que cuadran y una fila con la aritmética rota."""
    extracto = ExtractoCrudo(
        compras=Decimal("1000"),
        abonos=Decimal("300"),
        saldo_anterior=Decimal("500"),
        pago_total=Decimal("1200"),
        movimientos=[
            MovimientoCrudo(
                fecha=date(2026, 9, 1), descripcion="COMPRA BUENA", valor=Decimal("1000")
            ).cerrar(),
            MovimientoCrudo(
                fecha=date(2026, 9, 2), descripcion="PAGO", valor=Decimal("-300")
            ).cerrar(),
            # Cuota 100 con 5 cuotas por delante y 4.500 de capital: la cuota no cubre
            # el capital (4.500 / 5 = 900), así que una columna se leyó mal
            MovimientoCrudo(
                fecha=date(2026, 9, 3),
                descripcion="COMPRA MAL LEIDA",
                valor=Decimal("0"),
                cuota_mes=Decimal("100"),
                cuotas_n=5,
                cuotas_total=10,
                valor_pendiente=Decimal("4500"),
            ).cerrar(),
        ],
    )
    checks = {c["nombre"]: c for c in conciliar(extracto)}
    assert checks["compras del periodo"]["ok"] is True
    assert checks["pagos y abonos"]["ok"] is True
    assert checks["pago total"]["ok"] is True
    cuotas = checks["coherencia de las cuotas (la cuota cubre el capital que queda)"]
    assert cuotas["ok"] is False
    assert cuotas["filas_dudosas"][0]["descripcion"] == "COMPRA MAL LEIDA"
    assert conciliacion_ok(list(checks.values())) is False


def test_la_cuota_con_intereses_es_coherente():
    """La cuota incluye intereses y el pendiente es **capital**: eso no es un error.

    Es el caso real de una compra a 25 cuotas en el extracto de Amex: la cuota
    (17.304,50) es mayor que el capital que reparte (242.263,00 / 18 = 13.459,06) porque
    lleva los intereses. El control tiene que aceptarlo, no marcar la fila.
    """
    extracto = ExtractoCrudo(
        movimientos=[
            MovimientoCrudo(
                fecha=date(2026, 2, 15),
                descripcion="COMPRA A CUOTAS",
                valor=Decimal("415308.00"),
                cuota_mes=Decimal("17304.50"),
                cuotas_n=7,
                cuotas_total=25,
                valor_pendiente=Decimal("242263.00"),
            ).cerrar()
        ]
    )
    cuotas = [
        c for c in conciliar(extracto) if c["nombre"].startswith("coherencia de las cuotas")
    ][0]
    assert cuotas["ok"] is True, cuotas["filas_dudosas"]
    assert cuotas["calculado"] == "1"


def _excel_amex() -> bytes:
    """Un libro como el de Amex, pero con datos inventados: dos tablas y dos monedas."""
    import openpyxl

    libro = openpyxl.Workbook()
    for nombre, moneda, compra, cuota, abono, ant_valor, ant_cuota, ant_pend in (
        ("PESOS", "COP", "24.900,00", "24.900,00", "-974.993,00", "1.095.653,00", "73.043,53", "821.739,74"),
        ("DOLARES", "USD", "10,54", "10,54", "-4,77", "156,42", "26,07", "104,28"),
    ):
        hoja = libro.create_sheet(nombre) if nombre != "Sheet" else libro.active
        hoja.title = nombre
        hoja.append(["Información Cliente:"])
        hoja.append(["Moneda:", moneda])
        hoja.append(["Pago mínimo", "1.000,00"])
        hoja.append(["Pago total", "5.000,00"])
        hoja.append(["Periodo facturado", "17 ago", "15 sep. 2026"])
        hoja.append(["Pagar antes de", "30 sep. 2026"])
        hoja.append(["Cupo total", "1.000.000,00"])
        hoja.append(["Tienes disponible", "750.000,00"])
        hoja.append([])
        hoja.append(["Movimientos durante el periodo"])
        hoja.append(
            ["Número de autorización", "Fecha", "Movimientos", "Valor Movimiento",
             "Número de cuotas", "Valor cuota/abono", "Saldo pendiente"]
        )
        hoja.append(["111", "11/09/2026", "AMAZON.COM", compra, "1/1", cuota, "0,00"])
        hoja.append(["222", "04/09/2026", "ABONO SUCURSAL VIRTUAL", abono, "", abono, "0,00"])
        hoja.append([])
        hoja.append(["Movimientos antes del periodo"])
        hoja.append(
            ["Número de autorización", "Fecha", "Movimientos", "Valor Movimiento",
             "Número de cuotas", "Valor cuota/abono", "Saldo pendiente"]
        )
        hoja.append(["333", "18/03/2026", "AMAZON.COM", ant_valor, "6/24", ant_cuota, ant_pend])
    if "Sheet" in libro.sheetnames:
        del libro["Sheet"]
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def test_leer_un_excel_de_punta_a_punta():
    """El Excel es el camino exacto: se lee, se marca lo viejo y se concilia."""
    contenido = _excel_amex()
    hojas = dict(leer_excel(contenido))
    assert set(hojas) == {"PESOS", "DOLARES"}

    extracto, texto = parsear(contenido, "extracto.xlsx")
    assert "PESOS" in texto and "DOLARES" in texto
    assert extracto.moneda == "COP"
    assert extracto.pago_minimo == Decimal("1000.00")
    assert extracto.pago_total == Decimal("5000.00")

    # 4 movimientos: 2 del periodo por hoja; los 2 de "antes del periodo" son informativos
    assert len(extracto.movimientos) == 6
    informativos = [m for m in extracto.movimientos if m.es_informativo]
    assert len(informativos) == 2, "lo anterior al periodo no es gasto nuevo"

    # Cada hoja conserva su moneda: una compra de 24.900 COP y otra de 10,54 USD
    monedas = {(m.moneda, m.valor) for m in extracto.movimientos if m.tipo == "compra"}
    assert (("COP", Decimal("24900.00")) in monedas)
    assert (("USD", Decimal("10.54")) in monedas)

    # El pago se clasifica como pago, no como compra
    pagos = [m for m in extracto.movimientos if m.tipo == "pago"]
    assert {m.moneda for m in pagos} == {"COP", "USD"}


def test_marcar_informativos_por_periodo():
    """Lo que cae fuera del periodo declarado no se importa como gasto nuevo."""
    extracto = ExtractoCrudo(
        periodo_desde=date(2026, 8, 17),
        periodo_hasta=date(2026, 9, 15),
        movimientos=[
            MovimientoCrudo(fecha=date(2026, 9, 1), descripcion="NUEVA", valor=Decimal("100")).cerrar(),
            MovimientoCrudo(fecha=date(2026, 3, 1), descripcion="VIEJA", valor=Decimal("200")).cerrar(),
        ],
    )
    marcar_informativos(extracto)
    assert [m.es_informativo for m in extracto.movimientos] == [False, True]


def test_pdf_sin_tabla_avisa_en_vez_de_inventar():
    """Un PDF que no es un extracto no debe producir movimientos falsos."""
    from pypdf import PdfWriter

    escritor = PdfWriter()
    escritor.add_blank_page(width=612, height=792)
    buffer = io.BytesIO()
    escritor.write(buffer)
    pdf = buffer.getvalue()
    extracto, _ = parsear(pdf, "carta.pdf")
    assert extracto.movimientos == []
    assert any("No se reconoció la tabla" in a for a in extracto.avisos)
