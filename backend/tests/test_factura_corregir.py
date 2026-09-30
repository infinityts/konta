"""Corregir el monto y la fecha que detectó el lector (la otra mitad del paracaídas)."""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar


def _factura(client, h, texto: str = "RECIBO\nTOTAL 10.000\n") -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_se_puede_corregir_el_monto_y_la_fecha(client):
    _, h = _registrar(client)
    factura = _factura(client, h)
    r = client.patch(
        f"/facturas/{factura['id']}",
        headers=h,
        json={"monto_detectado": "844041", "fecha_detectada": "2026-09-30"},
    )
    assert r.status_code == 200, r.text
    assert Decimal(str(r.json()["monto_detectado"])) == Decimal("844041")
    assert r.json()["fecha_detectada"] == "2026-09-30"

    # queda guardado
    guardada = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert Decimal(str(guardada["monto_detectado"])) == Decimal("844041")


def test_la_auditoria_usa_el_monto_corregido(client):
    """El descuadre se calcula contra el monto **corregido**, no contra el del lector."""
    _, h = _registrar(client)
    factura = _factura(client, h)          # el lector detectó 10.000
    tx = client.post(
        "/transacciones",
        headers=h,
        json={"tipo": "gasto", "monto": "844041", "fecha": "2026-09-30", "descripcion": "EMCALI"},
    ).json()

    # sin corregir: no cuadra (10.000 contra 844.041)
    r = client.post(f"/facturas/{factura['id']}/asociar", headers=h, json={"transaccion_id": tx["id"]})
    assert Decimal(str(r.json()["descuadre"])) == Decimal("834041")  # 844.041 - 10.000

    # el usuario corrige el monto y la auditoría pasa a cuadrar
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "844041"})
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert Decimal(str(detalle["descuadre"])) == Decimal("0")
    assert Decimal(str(detalle["transaccion_monto"])) == Decimal("844041")


def test_se_puede_borrar_el_monto_detectado(client):
    """Un recibo ilegible: mejor sin monto que con uno inventado."""
    _, h = _registrar(client)
    factura = _factura(client, h)
    r = client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": None})
    assert r.status_code == 200, r.text
    assert r.json()["monto_detectado"] is None
    # y la fecha sigue intacta (no se tocó)
    assert client.get(f"/facturas/{factura['id']}", headers=h).json()["fecha_detectada"] == (
        factura["fecha_detectada"]
    )


def test_el_monto_corregido_es_el_que_propone_registrar_el_gasto(client):
    """En un recibo sin artículos, «Registrar el gasto» usa el monto corregido."""
    _, h = _registrar(client)
    factura = _factura(client, h)          # 10.000 del lector
    # un texto sin artículos: la factura queda para registrarla como un solo gasto
    client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={"texto": "Pago de servicio\n"})
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "46477"})
    r = client.post(f"/facturas/{factura['id']}/confirmar-total", headers=h, json={})
    assert r.status_code == 200, r.text
    movimientos = client.get("/transacciones", headers=h).json()
    assert [Decimal(str(m["monto"])) for m in movimientos] == [Decimal("46477")]
