"""Un select vacío de la pantalla no puede tumbar el registro de un gasto.

Pasó de verdad: en un recibo **sin artículos** (una captura que no se parte), pulsar
«Registrar el gasto» devolvía **422** porque la pantalla mandaba `categoria_id: ""` — el `??`
de JavaScript no salta con la cadena vacía, así que el `""` llegaba al backend y no es un UUID.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar


def _recibo_sin_articulos(client, h) -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("recibo.pdf", _pdf_minimo("RECIBO\nTOTAL 12.000\n"), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_confirmar_total_acepta_los_campos_vacios(client):
    _, h = _registrar(client)
    factura = _recibo_sin_articulos(client, h)
    r = client.post(
        f"/facturas/{factura['id']}/confirmar-total",
        headers=h,
        json={"categoria_id": "", "etiqueta_id": "", "cuenta_id": "", "tarjeta_id": ""},
    )
    assert r.status_code == 200, r.text

    movimientos = client.get("/transacciones", headers=h).json()
    montos = [Decimal(str(m["monto"])) for m in movimientos]
    assert Decimal("12000") in montos, "el gasto no quedó registrado"


def test_sigue_rechazando_un_uuid_que_no_existe(client):
    """Tolerar el vacío no es tolerar cualquier cosa."""
    _, h = _registrar(client)
    factura = _recibo_sin_articulos(client, h)
    r = client.post(
        f"/facturas/{factura['id']}/confirmar-total",
        headers=h,
        json={"categoria_id": "no-es-un-uuid"},
    )
    assert r.status_code == 422
