"""Recibo **fotografiado**: OCR de una foto, tipo de documento y gasto sin artículos.

El texto de este módulo es el OCR **real** de la foto de un parqueadero (Midas Park,
2026-09-29). Se usa como constante para probar el tratamiento del ruido sin depender de
tesseract: el OCR mete la cabecera y el pie del recibo (NIT, dirección, correo, número de
resolución) y antes de los arreglos eso producía seis «artículos» que no eran artículos.
"""

from __future__ import annotations

from test_api import _pdf_minimo, _registrar

from app.facturas import detectar_fecha, detectar_monto
from app.lineas import detectar_tipo, parsear_lineas

OCR_PARQUEADERO = """Midas Park Ss.AS.
NT 901349195-5
REGIMEN COMUN
Documento equivalente POS
No: POSE-85701
Avenida 6a $ 2110-47
midasparking2gmall.com
3502049720
Fecha: 2026-09-29 10:28:03
Ingreso: 2026-09-29 09:56:56
Matrícula:
Duración: On 30m 19s
Operario: MidasKiosko1
Método de pago: Efectivo
Subtotal: $ 3.445
IVA: $ 655
TOTAL: $ 4.100
Recibido: $ 5.000
: $ 900
c5803054e30fdbeb
278da301374
Ae: consumidor final
) ción: 18764116142437
s por su visital
PARKING
S MAS SAS.
"""


def test_el_monto_y_la_fecha_se_leen_de_la_foto():
    assert detectar_monto(OCR_PARQUEADERO) == 4100
    assert str(detectar_fecha(OCR_PARQUEADERO)) == "2026-09-29"


def test_el_recibo_de_parqueadero_no_inventa_articulos():
    """La cabecera del recibo (NIT, dirección, correo, resolución) no son artículos."""
    arts = parsear_lineas(OCR_PARQUEADERO)
    assert arts == [], [a["descripcion"] for a in arts]
    assert detectar_tipo(OCR_PARQUEADERO, arts) == "parqueadero"


def test_la_cabecera_de_una_foto_no_es_un_articulo():
    """Sin el filtro, «NIT 901349195» o la resolución se colaban como artículos."""
    from decimal import Decimal

    from app.lineas import _linea_plausible

    assert _linea_plausible("Midas Park Ss.AS", Decimal("901349195")) is False  # NIT gigante
    assert _linea_plausible("midasparking2gmall.com", Decimal("3502049720")) is False
    assert _linea_plausible("No: POSE", Decimal("85701")) is False
    assert _linea_plausible(") ción", Decimal("18764116142437")) is False
    assert _linea_plausible("FILETE PECHUGA BUCANERO", Decimal("33854")) is True


def test_un_recibo_de_servicio_se_registra_como_un_solo_gasto(client):
    """Sin artículos, «registrar el gasto» usa el total detectado de la foto."""
    _, h = _registrar(client)
    cats = {c["nombre"]: c["id"] for c in client.get("/categorias", headers=h).json()}
    etqs = {e["nombre"]: e["id"] for e in client.get("/etiquetas", headers=h).json()}
    assert "Parqueadero" in etqs, "la etiqueta Parqueadero se siembra sola"

    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo(OCR_PARQUEADERO), "application/pdf")}
    ).json()
    detalle = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={}).json()
    assert detalle["lineas"] == []
    assert detalle["tipo_documento"] == "parqueadero"

    r = client.post(
        f"/facturas/{f['id']}/confirmar-total",
        headers=h,
        json={"categoria_id": cats["Transporte"], "etiqueta_id": etqs["Parqueadero"]},
    )
    assert r.status_code == 200, r.text

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 1, txs
    assert float(txs[0]["monto"]) == 4100.0
    assert txs[0]["etiqueta_id"] == etqs["Parqueadero"]


def test_la_subida_le_pasa_el_nombre_y_el_tipo_al_extractor(client, monkeypatch):
    """El bug real: `extraer_texto` se llamaba sin nombre ni tipo, así que un JPG se
    trataba como PDF y la foto quedaba sin texto (monto `—` y 400 al leer líneas)."""
    import app.routers.facturas as R

    llamadas: list[tuple[str, str | None]] = []
    real = R.extraer_texto

    def espia(contenido, nombre="", content_type=None, password=None):
        llamadas.append((nombre, content_type))
        return real(contenido, nombre, content_type, password)

    monkeypatch.setattr(R, "extraer_texto", espia)
    _, h = _registrar(client)
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("WhatsApp Image.jpeg", b"\xff\xd8\xff\xe0datos", "image/jpeg")},
    )
    assert r.status_code == 201, r.text
    assert llamadas == [("WhatsApp Image.jpeg", "image/jpeg")]


def test_una_foto_ilegible_avisa_que_es_el_ocr(client):
    """Sin texto y siendo foto, el mensaje habla del OCR (no de «súbela de nuevo»)."""
    _, h = _registrar(client)
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("foto.jpeg", b"\xff\xd8\xff\xe0nada", "image/jpeg")},
    ).json()
    r = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={})
    assert r.status_code == 400
    assert "OCR" in r.json()["detail"] or "foto" in r.json()["detail"].lower()


# El pie del recibo, tal como el OCR de producción lo convirtió en «artículos»:
# «Eta $2.026», «SE Rango desde $85.550» y «asta $500.000».
OCR_PARQUEADERO_RUIDO = OCR_PARQUEADERO + "Eta 2.026\nSE Rango desde 85.550\nHasta 500.000\n"

URL_QR = (
    "https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey="
    "75d42c2ee77b714f7431e708c5803054e30fdbebe5190abe65eadc265ef297238c55278da30137409ac3fa5e6b36cd53"
)
CUDE = "75d42c2ee77b714f7431e708c5803054e30fdbebe5190abe65eadc265ef297238c55278da30137409ac3fa5e6b36cd53"


def test_el_pie_del_recibo_no_se_convierte_en_articulos():
    """El rango del POS («Hasta 500000») y los trozos cortos no son artículos."""
    arts = parsear_lineas(OCR_PARQUEADERO_RUIDO)
    assert arts == [], [a["descripcion"] for a in arts]


def test_el_cude_y_el_enlace_salen_del_qr():
    from app.qr import cude_de_url, url_dian

    assert cude_de_url(URL_QR) == CUDE
    assert cude_de_url(CUDE) == CUDE
    assert cude_de_url(None) is None
    assert cude_de_url("https://otra.com/x") is None
    assert url_dian(URL_QR) == URL_QR
    assert url_dian("nada") is None


def test_la_subida_guarda_el_cude_y_avisa_del_duplicado(client, monkeypatch):
    """El CUDE del QR no depende del OCR y delata la misma factura subida dos veces."""
    import app.routers.facturas as R

    monkeypatch.setattr(R, "qr_de_documento", lambda *a, **k: URL_QR)
    _, h = _registrar(client)

    datos = {"archivo": ("f.pdf", _pdf_minimo(OCR_PARQUEADERO), "application/pdf")}
    primera = client.post("/facturas", headers=h, files=datos).json()
    assert primera["cude"] == CUDE
    assert primera["url_dian"] == URL_QR
    assert primera["duplicada"] is False

    segunda = client.post("/facturas", headers=h, files=datos).json()
    assert segunda["duplicada"] is True, "misma factura, mismo CUDE"
    assert segunda["cude"] == CUDE


def test_un_recibo_de_parqueadero_no_crea_lineas_en_el_endpoint(client):
    """El texto con ruido tampoco llega a la tabla: es un recibo de servicio."""
    _, h = _registrar(client)
    f = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo(OCR_PARQUEADERO_RUIDO), "application/pdf")},
    ).json()
    d = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={}).json()
    assert d["tipo_documento"] == "parqueadero"
    assert d["lineas"] == []
    assert float(d["monto_detectado"]) == 4100.0
