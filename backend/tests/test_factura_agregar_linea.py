"""Añadir un artículo a mano y reordenar las líneas.

El lector puede saltarse un renglón (o leer mal la mitad): sin poder añadirlo desde la app,
el detalle queda mintiendo y la suma no da el total de la factura.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

TEXTO = "PILAS AA 7.300\nLECHE ENTERA 4.500\nTOTAL 11.800\n"


def _factura_con_lineas(client, h) -> tuple[dict, dict]:
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo(TEXTO), "application/pdf")},
    ).json()
    detalle = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": TEXTO}).json()
    assert len(detalle["lineas"]) == 2
    return f, detalle


def test_se_puede_anadir_un_articulo_a_mano(client):
    _, h = _registrar(client)
    factura, detalle = _factura_con_lineas(client, h)

    r = client.post(
        f"/facturas/{factura['id']}/lineas/agregar",
        headers=h,
        json={"descripcion": "PAN TAJADO", "valor_total": "3200"},
    )
    assert r.status_code == 200, r.text
    lineas = r.json()["lineas"]
    assert len(lineas) == 3
    nueva = [li for li in lineas if "PAN TAJADO" in li["descripcion"].upper()][0]
    assert Decimal(str(nueva["valor_total"])) == Decimal("3200")
    # queda la última y sin transacción (pendiente de confirmar)
    assert nueva["orden"] == max(li["orden"] for li in lineas)
    assert nueva["transaccion_id"] is None

    # y la suma del detalle ya incluye el artículo nuevo
    assert sum(Decimal(str(li["valor_total"])) for li in lineas) == Decimal("15000")


def test_se_puede_anadir_con_etiqueta_y_queda_como_manual(client):
    _, h = _registrar(client)
    factura, _ = _factura_con_lineas(client, h)
    # igual que el resto de los tests: la etiqueta se crea por su nombre
    etq = client.post("/etiquetas", headers=h, json={"nombre": "Despensa"}).json()

    r = client.post(
        f"/facturas/{factura['id']}/lineas/agregar",
        headers=h,
        json={"descripcion": "ARROZ", "valor_total": "5000", "etiqueta_id": etq["id"]},
    )
    assert r.status_code == 200, r.text
    nueva = [li for li in r.json()["lineas"] if "ARROZ" in li["descripcion"].upper()][0]
    assert nueva["etiqueta_id"] == etq["id"]
    assert nueva["origen"] == "agregada", "una línea puesta a mano se marca como agregada"


def test_reordenar_las_lineas(client):
    _, h = _registrar(client)
    factura, detalle = _factura_con_lineas(client, h)
    ids = [li["id"] for li in detalle["lineas"]]

    r = client.put(
        f"/facturas/{factura['id']}/lineas/orden",
        headers=h,
        json={"linea_ids": list(reversed(ids))},
    )
    assert r.status_code == 200, r.text
    assert [li["id"] for li in r.json()["lineas"]] == list(reversed(ids))


def test_reordenar_rechaza_lineas_de_otra_factura(client):
    _, h = _registrar(client)
    _, detalle = _factura_con_lineas(client, h)
    otra, _ = _factura_con_lineas(client, h)
    r = client.put(
        f"/facturas/{otra['id']}/lineas/orden",
        headers=h,
        json={"linea_ids": [li["id"] for li in detalle["lineas"]]},
    )
    assert r.status_code == 404, r.text


def test_volver_a_leer_no_borra_lo_que_puse_a_mano(client):
    """El re-parseo respeta el trabajo del usuario (y no lo duplica)."""
    _, h = _registrar(client)
    factura, detalle = _factura_con_lineas(client, h)
    r = client.post(
        f"/facturas/{factura['id']}/lineas/agregar",
        headers=h,
        json={"descripcion": "PAN TAJADO", "valor_total": "3200"},
    )
    assert len(r.json()["lineas"]) == 3

    otra = client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={"texto": TEXTO}).json()
    descripciones = [li["descripcion"].upper() for li in otra["lineas"]]
    assert sum(1 for d in descripciones if "PAN TAJADO" in d) == 1, "se perdió o se duplicó"
    assert sum(1 for d in descripciones if "PILAS" in d) == 1
