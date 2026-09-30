"""Si el monto detectado no es de fiar, la app lo dice (no lo esconde).

El caso que lo motivó: una confirmación de pago subida con una versión anterior del lector
quedó con un monto de 695.417.658 (el CUS) y la lista lo mostraba tan tranquila.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar


def _factura(client, h, texto: str) -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_avisa_cuando_el_monto_sale_de_un_numero_de_documento(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "Monto: $46.477\n")
    # el usuario (o una versión vieja del lector) deja el CUS como monto
    r = client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "695417658"})
    assert r.status_code == 200, r.text
    assert r.json()["aviso_monto"], "debería avisar"

    # y aparece también en la lista, sin tener que abrir el detalle
    en_lista = [f for f in client.get("/facturas", headers=h).json() if f["id"] == factura["id"]][0]
    assert en_lista["aviso_monto"], "el aviso tiene que verse en la lista"


def test_avisa_cuando_el_monto_no_cuadra_con_los_articulos(client):
    _, h = _registrar(client)
    texto = "PILAS AA 7.300\nLECHE ENTERA 4.500\nTOTAL 11.800\n"
    factura = _factura(client, h, texto)
    client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={"texto": texto})
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    # el lector vio 11.800 y los artículos suman 11.800: sin aviso
    assert detalle["aviso_monto"] is None, detalle["aviso_monto"]

    # ahora el monto queda en 900.000: no cuadra con los 11.800 de los artículos
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "900000"})
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert "no coincide con la suma" in (detalle["aviso_monto"] or "")


def test_una_factura_sana_no_avisa(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "Monto: $46.477\nFecha: 30/09/2026\n")
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert Decimal(str(detalle["monto_detectado"])) == Decimal("46477")
    assert detalle["aviso_monto"] is None, detalle["aviso_monto"]


def test_sin_monto_detectado_lo_dice(client):
    """Mejor decir «no pudimos leerlo» que dejar la factura en blanco sin explicación."""
    _, h = _registrar(client)
    factura = _factura(client, h, "documento sin cifras\n")
    aviso = client.get(f"/facturas/{factura['id']}", headers=h).json()["aviso_monto"]
    assert aviso and "No pudimos leer el monto" in aviso


def test_los_impuestos_no_disparan_el_aviso(client):
    """Con IVA las líneas no suman el total y eso es normal: no se avisa."""
    _, h = _registrar(client)
    texto = "PRODUCTO A 100.000\nIVA 19.000\nTOTAL 119.000\n"
    factura = _factura(client, h, texto)
    client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={"texto": "PRODUCTO A 100.000\n"})
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "119000"})
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert detalle["aviso_monto"] is None, detalle["aviso_monto"]
