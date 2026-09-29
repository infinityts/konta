"""IVA y bloque tributario: extraer, conciliar, guardar y marcar cada línea."""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

from app.impuestos import detectar_impuestos
from app.lineas import parsear_lineas

# El bloque tributario de la factura real de Cañaveral (concilia al peso).
BLOQUE = """
Vta Gravada (*)....... 460,210 +
Vta Exenta (**)....... 301,198 +
Vta Excluida ....... 433,792 +
Dscto Lista (D)....... 85,565 -
Impuestos .......... 78,613 +
IVA del 5% 5.00 42,959 2,148
IVA del 19% 19.00 397,067 75,443
ICO Bolsa 0.00 0 1,022
"""

# Factura pequeña con marca de IVA en cada línea: `**` exento, `*` gravado, sin marca excluido.
FACTURA = """SUPERTIENDAS EJEMPLO
Fecha : 2026/9/16
----------------------------------------
Item Descripcion de Item
Referencia Cant. U.M V/r Uni. Total
----------------------------------------
1 FILETE PECHUGA BUCANERO A GRANEL
023029 1.372 kg 24,674 33,854**
2 BOLSA EJEMPLO MATERIAL RECICL
0038007 4.00 un 300 1,200*
3 QUESO EJEMPLO PARMESANO
000977 1.00 un 32,700 32,700
----------------------------------------
T O T A L ............ $67,754
TOTAL ITEMS........... 3
Vta Gravada (*)....... 1,200 +
Vta Exenta (**)....... 33,854 +
Vta Excluida ....... 32,700 +
Dscto Lista (D)....... 0 -
Impuestos .......... 228 +
IVA del 19% 19.00 1,200 228
ICO Bolsa 0.00 0 0
"""


def test_detectar_impuestos_concilia_la_factura_real():
    r = detectar_impuestos(BLOQUE)
    assert r is not None
    assert r["descuento"] == Decimal("85565")
    assert r["gravada"] == Decimal("460210")
    assert r["exenta"] == Decimal("301198")
    assert r["excluida"] == Decimal("433792")
    assert r["impuestos_total"] == Decimal("78613")
    assert {d["nombre"]: d["valor"] for d in r["detalle"]} == {
        "IVA": Decimal("75443"),
        "ICO": Decimal("1022"),
    }
    assert r["conciliado"] is True, "2.148 + 75.443 + 1.022 = 78.613"


def test_el_bloque_se_guarda_al_subir_la_factura(client):
    _, h = _registrar(client)
    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo(FACTURA), "application/pdf")}
    ).json()
    assert float(f["impuestos_total"]) == 228.0
    assert float(f["iva_valor"]) == 228.0  # el IVA, sin el ICO
    assert float(f["descuento"]) == 0.0
    assert f["impuestos_detalle"] is not None


def test_cada_linea_queda_marcada_con_su_tratamiento():
    arts = parsear_lineas(FACTURA)
    por_desc = {a["descripcion"]: a.get("iva_tipo") for a in arts}
    assert por_desc["FILETE PECHUGA BUCANERO A GRANEL"] == "exento"  # **
    assert por_desc["BOLSA EJEMPLO MATERIAL RECICL"] == "gravado"  # *
    assert por_desc["QUESO EJEMPLO PARMESANO"] == "excluido"  # sin marca


def test_sin_bloque_tributario_no_hay_impuestos(client):
    _, h = _registrar(client)
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo("TIENDA VARIOS\nPILAS AA 7.300\n"), "application/pdf")},
    ).json()
    assert f["impuestos_total"] is None
    assert f["iva_valor"] is None
