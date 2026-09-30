"""El modo revisión: la factura dice si el monto, la fecha y los artículos están bien.

La fecha decide en **qué mes** cae el gasto, así que una fecha que falta o que está en el
futuro descoloca los reportes sin que se note.
"""

from __future__ import annotations

from datetime import timedelta

from test_api import _pdf_minimo, _registrar

from app.recurrencia import hoy


def _factura(client, h, texto: str) -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_avisa_cuando_no_hay_fecha(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "Monto: $46.477\n")
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert detalle["aviso_fecha"] and "No pudimos leer la fecha" in detalle["aviso_fecha"]


def test_avisa_cuando_la_fecha_esta_en_el_futuro(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "Monto: $46.477\n")
    futuro = (hoy() + timedelta(days=90)).isoformat()
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"fecha_detectada": futuro})
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert detalle["aviso_fecha"] and "futuro" in detalle["aviso_fecha"]


def test_una_fecha_normal_no_avisa(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "Monto: $46.477\nFecha: 30/09/2026\n")
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert detalle["fecha_detectada"] == "2026-09-30", detalle["fecha_detectada"]
    assert detalle["aviso_fecha"] is None, detalle["aviso_fecha"]


def test_el_aviso_de_la_fecha_tambien_esta_en_la_lista(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "documento sin fecha\n")
    en_lista = [f for f in client.get("/facturas", headers=h).json() if f["id"] == factura["id"]][0]
    assert en_lista["aviso_fecha"], "el panel de revisión lo necesita sin abrir el detalle"
