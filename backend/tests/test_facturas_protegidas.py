"""Subir una factura electrónica en **PDF protegido** (la clave suele ser el NIT del emisor).

Antes, un PDF con contraseña devolvía texto vacío y la app decía «no tiene texto extraído»:
no se distinguía «no se pudo leer» de «viene con contraseña».
"""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from test_api import _pdf_minimo, _registrar

CLAVE = "805028041"


def _pdf_protegido(texto: str, clave: str = CLAVE) -> bytes:
    """El PDF mínimo de los tests, pero cifrado con contraseña."""
    lector = PdfReader(io.BytesIO(_pdf_minimo(texto)))
    escritor = PdfWriter()
    for pagina in lector.pages:
        escritor.add_page(pagina)
    escritor.encrypt(clave)
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def _subir(client, h, contenido: bytes, **campos):
    return client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("factura.pdf", contenido, "application/pdf")},
        data=campos,
    )


def test_sin_contrasena_avisa_que_esta_protegido(client):
    """El mensaje habla de la contraseña, no de un texto que no se pudo extraer."""
    _, h = _registrar(client)
    r = _subir(client, h, _pdf_protegido("FACTURA TOTAL 250.000"))
    assert r.status_code == 400, r.text
    assert "protegido" in r.json()["detail"].lower()


def test_con_la_contrasena_equivocada_tambien_avisa(client):
    _, h = _registrar(client)
    r = _subir(client, h, _pdf_protegido("FACTURA TOTAL 250.000"), contrasena="000000")
    assert r.status_code == 400
    assert "contraseña" in r.json()["detail"].lower()


def test_con_la_contrasena_correcta_se_lee_la_factura(client):
    _, h = _registrar(client)
    r = _subir(client, h, _pdf_protegido("FACTURA TOTAL 250.000"), contrasena=CLAVE)
    assert r.status_code == 201, r.text
    datos = r.json()
    assert "TOTAL" in (datos["texto_extraido"] or "").upper()
    assert float(datos["monto_detectado"]) == 250000.0


def test_un_pdf_sin_contrasena_sigue_funcionando(client):
    """Sin contraseña de por medio no cambia nada."""
    _, h = _registrar(client)
    r = _subir(client, h, _pdf_minimo("FACTURA TOTAL 120.000"))
    assert r.status_code == 201, r.text
    assert float(r.json()["monto_detectado"]) == 120000.0
