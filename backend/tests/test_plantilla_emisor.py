"""La plantilla por emisor: la app se aprende el formato de cada uno.

No se puede ir a cada banco o establecimiento a pedirles un formato, pero sí se puede aprender:
cuando el usuario corrige el monto de un documento, se guarda **en qué etiqueta venía** («en los
documentos de este emisor el total está donde dice VALOR»), y la próxima factura del mismo
emisor se lee bien a la primera.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

# Un documento donde el lector **se equivoca**: hay dos números sin etiqueta de total y gana el
# más grande (120.000), cuando el valor de verdad es el de la línea «Valor» (50.000).
PRIMERA = "EMPRESA X S.A.\nNit 900123456-7\nValor 50000\nCuota 120000\n"
# El mismo emisor, el mes siguiente: la misma trampa, otro número
SEGUNDA = "EMPRESA X S.A.\nNit 900123456-7\nValor 60000\nCuota 130000\n"


def _subir(client, h, texto: str, nombre: str = "f.pdf") -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": (nombre, _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_detecta_al_emisor_por_su_nit():
    from app.facturas import detectar_emisor

    assert detectar_emisor(PRIMERA) == ("nit:9001234567", "EMPRESA X S.A.")
    assert detectar_emisor("1234\n5678\n") is None


def test_corregir_el_monto_ensena_la_plantilla(client):
    from decimal import Decimal as D

    _, h = _registrar(client)
    factura = _subir(client, h, PRIMERA)
    # el lector se equivocó: se quedó con el número más grande
    assert D(str(factura["monto_detectado"])) == D("120000")
    assert factura["emisor_nombre"] == "EMPRESA X S.A.", factura.get("emisor_nombre")

    # el usuario lo corrige y la app aprende dónde estaba el valor bueno
    r = client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "50000"})
    assert r.status_code == 200, r.text

    plantillas = client.get("/facturas/plantillas-lector", headers=h).json()
    guardada = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert len(plantillas) == 1, (
        f"no aprendió. emisor={guardada['emisor']!r} texto={guardada['texto_extraido']!r}"
    )
    assert plantillas[0]["emisor"] == "nit:9001234567"
    assert plantillas[0]["campo_monto"] == "VALOR"


def test_la_siguiente_factura_del_mismo_emisor_sale_bien_a_la_primera(client):
    """El criterio de la tarea: sin volver a corregir nada."""
    _, h = _registrar(client)
    primera = _subir(client, h, PRIMERA)
    client.patch(f"/facturas/{primera['id']}", headers=h, json={"monto_detectado": "50000"})

    segunda = _subir(client, h, SEGUNDA)
    assert Decimal(str(segunda["monto_detectado"])) == Decimal("60000"), segunda["monto_detectado"]
    # y sin el aviso de monto raro, porque el lector encontró el valor de verdad
    detalle = client.get(f"/facturas/{segunda['id']}", headers=h).json()
    assert detalle["aviso_monto"] is None, detalle["aviso_monto"]
    # la plantilla cuenta sus usos
    assert client.get("/facturas/plantillas-lector", headers=h).json()[0]["usos"] == 1


def test_el_usuario_puede_borrar_una_plantilla(client):
    _, h = _registrar(client)
    factura = _subir(client, h, PRIMERA)
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "50000"})
    plantilla = client.get("/facturas/plantillas-lector", headers=h).json()[0]

    assert client.delete(f"/facturas/plantillas-lector/{plantilla['id']}", headers=h).status_code == 204
    assert client.get("/facturas/plantillas-lector", headers=h).json() == []

    # y sin plantilla vuelve a equivocarse, que es lo honesto
    otra = _subir(client, h, SEGUNDA, nombre="f2.pdf")
    assert Decimal(str(otra["monto_detectado"])) == Decimal("130000")


def test_la_plantilla_guarda_la_fecha_y_el_tipo(client):
    _, h = _registrar(client)
    texto = "EMPRESA Y S.A.\nNit 900999888-1\nFecha de pago 30/09/2026\nValor 50000\nCuota 120000\n"
    factura = _subir(client, h, texto)
    client.patch(
        f"/facturas/{factura['id']}",
        headers=h,
        json={"monto_detectado": "50000", "fecha_detectada": "2026-09-30"},
    )
    plantilla = client.get("/facturas/plantillas-lector", headers=h).json()[0]
    assert plantilla["campo_monto"] == "VALOR"
    assert plantilla["campo_fecha"] == "FECHA DE PAGO"
