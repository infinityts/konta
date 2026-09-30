"""Renglones que no son artículos: los globales y los que el usuario borra siempre.

Un recibo trae «Nit: 900123456», «Cajero: 12» o «Cambio: 0» entre los renglones, y sin esto el
lector los toma por productos (el detalle queda con basura y la suma no cuadra).
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo, _registrar

RECIBO = """MERCADO LA 14
Nit: 900123456-7
PILAS AA 7.300
Cajero: 12
LECHE 4.500
Cambio: 0
TOTAL 11.800
"""

# Un renglón que el lector sí toma por artículo y el usuario va a borrar
CON_RUIDO = "PROMOCION DEL DIA 1.000\nPILAS AA 7.300\nLECHE 4.500\n"


def _factura(client, h, texto: str) -> dict:
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo(texto), "application/pdf")},
    ).json()
    return client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": texto}).json()


def test_los_renglones_del_documento_no_son_articulos(client):
    _, h = _registrar(client)
    detalle = _factura(client, h, RECIBO)
    descripciones = [li["descripcion"].upper() for li in detalle["lineas"]]
    assert len(descripciones) == 2, descripciones
    assert any("PILAS" in d for d in descripciones)
    assert not any("NIT" in d or "CAJERO" in d or "CAMBIO" in d for d in descripciones)


def test_lo_que_borras_dos_veces_se_descarta_solo(client):
    _, h = _registrar(client)
    # primera factura: el renglón basura entra, el usuario lo borra
    detalle = _factura(client, h, CON_RUIDO)
    basura = [li for li in detalle["lineas"] if "PROMOCION" in li["descripcion"].upper()]
    assert len(basura) == 1
    assert client.delete(f"/facturas/{detalle['id']}/lineas/{basura[0]['id']}", headers=h).status_code == 204

    # en la primera no basta (podría ser un error): vuelve a entrar
    otra = _factura(client, h, CON_RUIDO)
    assert any("PROMOCION" in li["descripcion"].upper() for li in otra["lineas"])
    basura = [li for li in otra["lineas"] if "PROMOCION" in li["descripcion"].upper()][0]
    client.delete(f"/facturas/{otra['id']}/lineas/{basura['id']}", headers=h)

    # a la segunda ya se descarta solo, y lo dice
    tercera = _factura(client, h, CON_RUIDO)
    assert not any("PROMOCION" in li["descripcion"].upper() for li in tercera["lineas"])
    assert "no son artículos" in (tercera["aviso"] or ""), tercera["aviso"]
    assert [li["descripcion"].upper() for li in tercera["lineas"]] == ["PILAS AA", "LECHE 4.500"][:0] + [
        li["descripcion"].upper() for li in tercera["lineas"]
    ]  # los dos artículos siguen ahí
    assert sum(Decimal(str(li["valor_total"])) for li in tercera["lineas"]) == Decimal("11800")


def test_el_usuario_puede_ver_y_borrar_lo_que_se_descarta(client):
    _, h = _registrar(client)
    detalle = _factura(client, h, CON_RUIDO)
    for _ in range(2):
        basura = [li for li in detalle["lineas"] if "PROMOCION" in li["descripcion"].upper()][0]
        client.delete(f"/facturas/{detalle['id']}/lineas/{basura['id']}", headers=h)
        detalle = _factura(client, h, CON_RUIDO)

    patrones = client.get("/facturas/patrones-ignorados", headers=h).json()
    assert len(patrones) == 1, patrones
    assert patrones[0]["patron"] == "PROMOCION DEL DIA"
    assert patrones[0]["veces"] >= 2

    # si el usuario borró algo que sí era un artículo, lo puede deshacer
    assert client.delete(f"/facturas/patrones-ignorados/{patrones[0]['id']}", headers=h).status_code == 204
    assert client.get("/facturas/patrones-ignorados", headers=h).json() == []
    cuarta = _factura(client, h, CON_RUIDO)
    assert any("PROMOCION" in li["descripcion"].upper() for li in cuarta["lineas"])


def test_el_patron_no_se_lleva_por_delante_otros_articulos(client):
    """Descartar «PROMOCION DEL DIA» no puede tocar «PROMOCION 2X1» ni el resto."""
    _, h = _registrar(client)
    detalle = _factura(client, h, CON_RUIDO)
    for _ in range(2):
        basura = [li for li in detalle["lineas"] if "DEL DIA" in li["descripcion"].upper()][0]
        client.delete(f"/facturas/{detalle['id']}/lineas/{basura['id']}", headers=h)
        detalle = _factura(client, h, CON_RUIDO)

    texto = "PROMOCION DEL DIA 1.000\nPROMOCION ESPECIAL 2.000\nPILAS AA 7.300\n"
    otra = _factura(client, h, texto)
    descripciones = [li["descripcion"].upper() for li in otra["lineas"]]
    # el patrón aprendido es el renglón completo («PROMOCION DEL DIA»), no la primera palabra
    assert not any("DEL DIA" in d for d in descripciones), descripciones
    assert any("ESPECIAL" in d for d in descripciones), descripciones
    assert sum(1 for li in otra["lineas"]) == 2, descripciones
