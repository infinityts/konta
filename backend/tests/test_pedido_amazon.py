"""Un pedido de Amazon en pesos: envío con descuento, comisión del cambio y **sin IVA**.

Es el caso que destapó tres cosas: el `CAMBIO` de la lista de ignoradas se comía la «Cuota
de garantía del tipo de cambio» (una comisión real), el menos que va **antes** del símbolo
(«-COP 38.456,49») no se capturaba y el envío gratis se sumaba como un cobro, y el patrón de
dinero paraba en el grupo de miles, así que `87,630.92` se leía como 87.630 (sin centavos).
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

PEDIDO = """Resumen del pedido
Productos: COP 87,630.92
Envio: COP 38,456.49
Envio gratis de Prime: -COP 38,456.49
Total antes de impuestos: COP 87,630.92
Impuestos: COP 0
Cuota de garantia del tipo de cambio: COP 1,971.70
Total (I.V.A. Incluido): COP 89,602.62
Tasa de cambio
1 USD = 3370.42 COP
"""


def test_las_lineas_cuadran_con_el_total():
    from app.lineas import parsear_lineas

    articulos = parsear_lineas(PEDIDO)
    assert [a["descripcion"] for a in articulos] == [
        "Productos",
        "Envio",
        "Envio gratis de Prime",
        "Cuota de garantia del tipo de cambio",
    ]
    assert sum(a["valor_total"] for a in articulos) == Decimal("89602.62")


def test_el_envio_gratis_va_en_negativo():
    """Si el descuento se leyera como cobro, el detalle saldría 76.912 de más."""
    from app.lineas import parsear_lineas

    articulos = {a["descripcion"]: a["valor_total"] for a in parsear_lineas(PEDIDO)}
    assert articulos["Envio gratis de Prime"] == Decimal("-38456.49")
    assert articulos["Envio"] == Decimal("38456.49")


def test_la_comision_del_cambio_no_se_pierde():
    """«Cuota de garantía del tipo de cambio» no es el «cambio» que devuelven en un recibo."""
    from app.lineas import parsear_lineas

    descripciones = [a["descripcion"] for a in parsear_lineas(PEDIDO)]
    assert "Cuota de garantia del tipo de cambio" in descripciones
    # pero el cambio de un recibo colombiano se sigue ignorando
    recibo = "LECHE ENTERA 4.200\nTOTAL 4.200\nEFECTIVO 10.000\nCAMBIO 5.800\n"
    assert [a["descripcion"] for a in parsear_lineas(recibo)] == ["LECHE ENTERA"]


def test_no_hay_iva_que_validar_en_esta_compra():
    """`Impuestos: COP 0`: la app no debe inventarse un IVA (ni tomarlo del total)."""
    from app.impuestos import detectar_impuestos

    assert detectar_impuestos(PEDIDO) is None


def test_confirmar_por_linea_no_crea_un_gasto_negativo(client):
    """El descuento es detalle de la factura, no un movimiento: no puede ir en negativo."""
    _, h = _registrar(client)
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("pedido.pdf", _pdf_minimo("PEDIDO AMAZON"), "application/pdf")},
    ).json()
    detalle = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": PEDIDO}).json()
    assert len(detalle["lineas"]) == 4

    r = client.post(f"/facturas/{f['id']}/confirmar", headers=h, json={})
    assert r.status_code == 200, r.text

    movimientos = client.get("/transacciones", headers=h).json()
    montos = [Decimal(str(m["monto"])) for m in movimientos]
    assert all(m > 0 for m in montos), f"se creó un movimiento en negativo: {montos}"
    # 4 líneas, una es un descuento: se crean 3 movimientos
    assert len(montos) == 3
