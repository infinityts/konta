"""Auditoría factura ↔ transacción: aviso de descuadre y de posible duplicado."""

from __future__ import annotations

from test_api import _pdf_minimo, _registrar


def test_asociar_avisa_si_no_cuadra(client):
    _, h = _registrar(client)
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo("FACTURA\nTOTAL 100.000\n"), "application/pdf")},
    ).json()
    assert float(f["monto_detectado"]) == 100000.0

    tx = client.post(
        "/transacciones",
        headers=h,
        json={"tipo": "gasto", "monto": "50000", "fecha": "2026-09-16", "descripcion": "otra compra"},
    ).json()

    r = client.post(f"/facturas/{f['id']}/asociar", headers=h, json={"transaccion_id": tx["id"]})
    assert r.status_code == 200, r.text
    assert "no cuadra" in r.json()["aviso"]
    assert float(r.json()["descuadre"]) == -50000.0

    # la ficha expone la comparación
    d = client.get(f"/facturas/{f['id']}", headers=h).json()
    assert float(d["transaccion_monto"]) == 50000.0
    assert float(d["descuadre"]) == -50000.0


def test_asociar_avisa_de_un_posible_duplicado(client):
    _, h = _registrar(client)
    texto = "PILAS AA 7.300\nTOTAL 7.300\n"
    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo(texto), "application/pdf")}
    ).json()
    client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": texto})
    client.post(f"/facturas/{f['id']}/confirmar", headers=h, json={})  # crea un gasto de 7.300

    # otra transacción del mismo valor → parece duplicado
    tx = client.post(
        "/transacciones",
        headers=h,
        json={"tipo": "gasto", "monto": "7300", "fecha": "2026-09-16", "descripcion": "duplicado"},
    ).json()
    r = client.post(f"/facturas/{f['id']}/asociar", headers=h, json={"transaccion_id": tx["id"]})
    assert r.status_code == 200, r.text
    assert "duplicado" in r.json()["aviso"]
