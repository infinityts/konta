"""Una compra = un movimiento: agrupado en el listado, detalle por etiqueta y unificar."""

from __future__ import annotations

from test_api import _pdf_minimo, _registrar

TEXTO = (
    "LECHE ALPINA*1000ml 30.900\n"
    "QUESO ALPINA*250g PARMESANO 32.700\n"
    "DESOD REXONA CLIN EXPERT 44.150\n"
)


def _subir_y_confirmar(client):
    _, h = _registrar(client)
    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo("factura"), "application/pdf")}
    ).json()
    r = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": TEXTO})
    assert r.status_code == 200, r.text
    assert len(r.json()["lineas"]) == 3
    r = client.post(f"/facturas/{f['id']}/confirmar", headers=h, json={})
    assert r.status_code == 200, r.text
    return h, f["id"]


def test_una_compra_es_un_solo_movimiento(client):
    """120 filas por un mercado no: las 3 líneas se agrupan en un movimiento."""
    h, fid = _subir_y_confirmar(client)

    planos = client.get("/transacciones", headers=h).json()
    assert len(planos) == 3, "confirmar línea por línea crea una transacción por artículo"

    movs = client.get("/transacciones/movimientos", headers=h).json()
    assert len(movs) == 1, movs
    m = movs[0]
    assert m["agrupada"] is True
    assert m["articulos"] == 3
    assert m["factura_id"] == fid
    assert float(m["monto"]) == 107750.0
    assert set(m["etiquetas"]) == {"Lácteos y huevos", "Cuidado personal"}


def test_detalle_agrupa_por_etiqueta_con_subtotales(client):
    h, fid = _subir_y_confirmar(client)

    d = client.get(f"/facturas/{fid}/detalle", headers=h).json()
    assert d["articulos"] == 3
    assert float(d["total"]) == 107750.0

    por_etiqueta = {g["etiqueta"]: g for g in d["grupos"]}
    lacteos = por_etiqueta["Lácteos y huevos"]
    assert len(lacteos["articulos"]) == 2
    assert float(lacteos["total"]) == 63600.0
    assert float(lacteos["porcentaje"]) == 59.0
    assert por_etiqueta["Cuidado personal"]["articulos"][0]["valor_unitario"] is None


def test_unificar_colapsa_en_un_movimiento_y_es_idempotente(client):
    h, fid = _subir_y_confirmar(client)

    r = client.post(f"/facturas/{fid}/unificar", headers=h)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["creada"] is True
    assert u["unificados"] == 3, u
    assert float(u["total"]) == 107750.0

    planos = client.get("/transacciones", headers=h).json()
    assert len(planos) == 1
    assert float(planos[0]["monto"]) == 107750.0

    # el detalle se conserva y sigue agrupado por etiqueta
    d = client.get(f"/facturas/{fid}/detalle", headers=h).json()
    assert d["articulos"] == 3

    # idempotente: no crea nada nuevo
    r2 = client.post(f"/facturas/{fid}/unificar", headers=h).json()
    assert r2["creada"] is False and r2["unificados"] == 0


def test_unificar_sin_confirmar_da_error_claro(client):
    _, h = _registrar(client)
    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo("factura"), "application/pdf")}
    ).json()
    r = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": TEXTO})
    assert r.status_code == 200
    r = client.post(f"/facturas/{f['id']}/unificar", headers=h)
    assert r.status_code == 400
    assert "confirm" in r.json()["detail"].lower()
