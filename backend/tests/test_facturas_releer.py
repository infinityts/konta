"""Volver a leer una factura **ya registrada** no puede duplicar sus líneas.

Pasó de verdad con una factura del mercado: se leyó (120 líneas), se registró como un
movimiento y, al volver a pulsar «Leer líneas» cinco horas después, el endpoint borró solo
las líneas **sin** movimiento —no había ninguna— e insertó otras 120: quedaron 240 y la suma
salía al doble del total.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

TEXTO = "PILAS AA 7.300\nLECHE ENTERA 4.500\nTOTAL 11.800\n"


def _factura(client, h, texto: str = TEXTO) -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("mercado.pdf", _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _leer(client, h, factura: dict, texto: str = TEXTO) -> dict:
    r = client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={"texto": texto})
    assert r.status_code == 200, r.text
    return r.json()


def test_releer_una_factura_registrada_no_duplica(client):
    _, h = _registrar(client)
    factura = _factura(client, h)

    primera = _leer(client, h, factura)
    lineas = len(primera["lineas"])
    assert lineas >= 2

    # se registra la compra como **un solo** movimiento con el total: las líneas pasan a
    # estar dentro del movimiento, que es lo que rompía la idempotencia
    r = client.post(f"/facturas/{factura['id']}/confirmar-total", headers=h, json={})
    assert r.status_code == 200, r.text

    segunda = _leer(client, h, factura)
    assert len(segunda["lineas"]) == lineas, "volver a leer duplicó las líneas"
    assert segunda["aviso"], "tiene que avisar de lo que se omitió"
    assert "no se duplicaron" in segunda["aviso"]

    # y la suma de las líneas sigue siendo la de la factura, no el doble
    suma = sum(Decimal(li["valor_total"]) for li in segunda["lineas"])
    assert suma == Decimal(factura["monto_detectado"])


def test_releer_con_un_articulo_nuevo_solo_agrega_ese(client):
    """Lo que ya estaba se omite; lo que aparece nuevo sí se añade."""
    _, h = _registrar(client)
    factura = _factura(client, h)
    primera = _leer(client, h, factura)
    client.post(f"/facturas/{factura['id']}/confirmar-total", headers=h, json={})

    con_nuevo = "PILAS AA 7.300\nLECHE ENTERA 4.500\nPAN TAJADO 3.000\nTOTAL 14.800\n"
    segunda = _leer(client, h, factura, con_nuevo)
    assert len(segunda["lineas"]) == len(primera["lineas"]) + 1
    assert any("PAN TAJADO" in li["descripcion"].upper() for li in segunda["lineas"])
    # las nuevas quedan **sin** movimiento, listas para confirmar
    nuevas = [li for li in segunda["lineas"] if li["transaccion_id"] is None]
    assert len(nuevas) == 1


def test_releer_sin_registrar_sigue_reemplazando(client):
    """Sin movimiento de por medio no cambia nada: se descarta lo anterior y se reescribe."""
    _, h = _registrar(client)
    factura = _factura(client, h)
    primera = _leer(client, h, factura)
    segunda = _leer(client, h, factura)
    assert len(segunda["lineas"]) == len(primera["lineas"])
    assert segunda["aviso"] is None
