"""El buzón de casos: «esta factura la leyó mal».

No se puede ir a cada establecimiento a pedirle un formato, pero sí se puede acumular lo que
falla: el caso guarda el texto, lo que dijo el lector, con qué se quedó el usuario y (si lo
autoriza) el archivo. De ahí sale un test.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

# Un documento donde el lector se equivoca (dos números sin etiqueta de total: gana el grande)
TEXTO = "EMPRESA X S.A.\nNit 900123456-7\nValor 50000\nCuota 120000\n"


def _factura(client, h, texto: str = TEXTO) -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("raro.pdf", _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_se_puede_reportar_una_factura_mal_leida(client):
    _, h = _registrar(client)
    factura = _factura(client, h)
    # el usuario la corrige y luego reporta que se leyó mal
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "50000"})
    r = client.post(
        f"/facturas/{factura['id']}/caso",
        headers=h,
        json={"motivo": "se quedó con el número de la cuota"},
    )
    assert r.status_code == 201, r.text
    caso = r.json()
    # el caso guarda las dos verdades: lo que dijo el lector y lo que dejó el usuario
    assert Decimal(str(caso["monto_leido"])) == Decimal("120000"), caso["monto_leido"]
    assert Decimal(str(caso["monto_corregido"])) == Decimal("50000")
    assert caso["emisor"] == "nit:9001234567"
    assert caso["emisor_nombre"] == "EMPRESA X S.A."
    assert "se quedó con el número" in caso["motivo"]
    assert caso["texto"].startswith("EMPRESA X")
    assert caso["estado"] == "abierto"
    assert caso["tiene_archivo"] is False


def test_el_archivo_solo_se_guarda_si_lo_autoriza(client):
    """Las facturas no guardan el archivo (solo el texto): se sube a propósito en el caso."""
    _, h = _registrar(client)
    factura = _factura(client, h)
    caso = client.post(f"/facturas/{factura['id']}/caso", headers=h, json={}).json()
    assert caso["tiene_archivo"] is False
    assert client.get(f"/facturas/casos/{caso['id']}/archivo", headers=h).status_code == 404

    subido = client.post(
        f"/facturas/casos/{caso['id']}/archivo",
        headers=h,
        files={"archivo": ("raro.pdf", _pdf_minimo(TEXTO), "application/pdf")},
    )
    assert subido.status_code == 200, subido.text
    assert subido.json()["tiene_archivo"] is True

    descarga = client.get(f"/facturas/casos/{caso['id']}/archivo", headers=h)
    assert descarga.status_code == 200
    assert descarga.content.startswith(b"%PDF")


def test_el_buzon_lista_y_resuelve(client):
    _, h = _registrar(client)
    factura = _factura(client, h)
    caso = client.post(f"/facturas/{factura['id']}/caso", headers=h, json={}).json()

    assert len(client.get("/facturas/casos", headers=h).json()) == 1
    assert len(client.get("/facturas/casos?estado=abierto", headers=h).json()) == 1
    assert client.get("/facturas/casos?estado=resuelto", headers=h).json() == []

    resuelto = client.post(f"/facturas/casos/{caso['id']}/resolver", headers=h).json()
    assert resuelto["estado"] == "resuelto"
    assert resuelto["resuelto_en"] is not None
    assert len(client.get("/facturas/casos?estado=abierto", headers=h).json()) == 0

    assert client.delete(f"/facturas/casos/{caso['id']}", headers=h).status_code == 204
    assert client.get("/facturas/casos", headers=h).json() == []


def test_el_caso_se_exporta_como_test(client):
    """El puente entre «esto se leyó mal» y «esto no se vuelve a romper»."""
    _, h = _registrar(client)
    factura = _factura(client, h)
    client.patch(f"/facturas/{factura['id']}", headers=h, json={"monto_detectado": "50000"})
    caso = client.post(f"/facturas/{factura['id']}/caso", headers=h, json={}).json()

    exportado = client.get(f"/facturas/casos/{caso['id']}/exportar", headers=h).json()
    assert Decimal(str(exportado["monto_leido"])) == Decimal("120000")
    assert Decimal(str(exportado["monto_esperado"])) == Decimal("50000")

    # la maqueta que se pega en tests/: texto tal cual + lo que se espera
    test = exportado["test"]
    assert "EMPRESA X S.A." in test and "Cuota 120000" in test
    assert 'Decimal("50000")' in test, test
    assert "def test_" in test
    # y compila: es un test de verdad
    compile(test, "<caso>", "exec")


def test_no_se_puede_reportar_una_factura_sin_texto(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "   ")
    r = client.post(f"/facturas/{factura['id']}/caso", headers=h, json={})
    assert r.status_code == 400, r.text
