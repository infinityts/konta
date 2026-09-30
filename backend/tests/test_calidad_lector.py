"""El panel de calidad: quién lee bien y quién no, por emisor.

Es lo que dice dónde invertir en vez de adivinar. Se apoya en dos datos que ahora se guardan por
factura: si hubo que **corregirla** y si salió bien **gracias a una plantilla** aprendida.
"""

from __future__ import annotations

from test_api import _pdf_minimo, _registrar

BUENO = "EMPRESA BUENA S.A.\nNit 900111222-3\nMonto: $46.477\nFecha: 30/09/2026\n"
MALO = "EMPRESA MALA S.A.\nNit 900444555-6\nValor 50000\nCuota 120000\n"


def _factura(client, h, texto: str, nombre: str = "f.pdf") -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": (nombre, _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_el_panel_cuenta_sin_correccion_frente_a_corregidas(client):
    _, h = _registrar(client)
    # dos documentos del mismo emisor: uno sale bien, el otro hay que corregirlo
    _factura(client, h, BUENO, "b1.pdf")
    malo = _factura(client, h, MALO, "m1.pdf")
    client.patch(f"/facturas/{malo['id']}", headers=h, json={"monto_detectado": "50000"})

    panel = client.get("/facturas/calidad-lector", headers=h).json()
    assert panel["documentos"] == 2
    assert panel["sin_correccion"] == 1
    assert panel["corregidas"] == 1

    por_emisor = {e["emisor"]: e for e in panel["emisores"]}
    buena = por_emisor["nit:9001112223"]
    assert (buena["documentos"], buena["sin_correccion"], buena["corregidas"]) == (1, 1, 0)
    mala = por_emisor["nit:9004445556"]
    assert (mala["documentos"], mala["sin_correccion"], mala["corregidas"]) == (1, 0, 1)
    assert mala["nombre"] == "EMPRESA MALA S.A."


def test_corregir_una_linea_tambien_cuenta_como_correccion(client):
    _, h = _registrar(client)
    factura = _factura(client, h, "PILAS AA 7.300\nLECHE 4.500\nTOTAL 11.800\n")
    # leer las líneas (sin cambiar el texto) NO es una corrección
    detalle = client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={}).json()
    assert client.get("/facturas/calidad-lector", headers=h).json()["corregidas"] == 0

    linea = detalle["lineas"][0]
    client.patch(
        f"/facturas/{factura['id']}/lineas/{linea['id']}", headers=h, json={"valor_total": "7300"}
    )
    assert client.get("/facturas/calidad-lector", headers=h).json()["corregidas"] == 1


def test_las_lecturas_con_plantilla_se_cuentan_aparte(client):
    """Una factura que sale bien por lo aprendido es un acierto del lector, no una corrección."""
    _, h = _registrar(client)
    primera = _factura(client, h, MALO, "m1.pdf")
    client.patch(f"/facturas/{primera['id']}", headers=h, json={"monto_detectado": "50000"})

    segunda = _factura(client, h, MALO, "m2.pdf")
    panel = client.get("/facturas/calidad-lector", headers=h).json()
    assert panel["con_plantilla"] == 1, panel
    assert panel["corregidas"] == 1  # la primera, que hubo que arreglar
    mala = [e for e in panel["emisores"] if e["emisor"] == "nit:9004445556"][0]
    assert (mala["documentos"], mala["sin_correccion"], mala["con_plantilla"]) == (2, 1, 1)


def test_los_casos_reportados_salen_en_el_panel(client):
    _, h = _registrar(client)
    factura = _factura(client, h, MALO, "m1.pdf")
    client.post(f"/facturas/{factura['id']}/caso", headers=h, json={"motivo": "se equivocó"})

    panel = client.get("/facturas/calidad-lector", headers=h).json()
    assert panel["casos_abiertos"] == 1
    mala = [e for e in panel["emisores"] if e["emisor"] == "nit:9004445556"][0]
    assert mala["casos"] == 1


def test_un_usuario_sin_facturas_ve_el_panel_vacio(client):
    _, h = _registrar(client)
    panel = client.get("/facturas/calidad-lector", headers=h).json()
    assert panel["documentos"] == 0
    assert panel["emisores"] == []
