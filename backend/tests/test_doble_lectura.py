"""La segunda opinión del OCR: se lee dos veces y gana la lectura más coherente.

No se puede pretender que un modo del OCR acierte con todos los documentos —el de una columna
mantiene cada etiqueta con su valor, el automático separa mejor las columnas de una tabla—,
así que cuando la primera lectura no trae un monto de fiar se pide otra y se compara.
"""

from __future__ import annotations

import pytesseract
from PIL import Image

from app.facturas import UMBRAL_REINTENTO, _mejor_lectura, puntaje_de_lectura

BUENA = "Gases de Occidente S.A. ESP\nMonto: $46.477\nFecha: 30/09/2026\n"
REVUELTA = "O)\n¡Pago realizado con éxito!\nDetalles del pago:\nNit:\nRazón social:\nMonto:\n"


def test_una_lectura_con_monto_de_fiar_puntua_mas():
    assert puntaje_de_lectura(BUENA) >= UMBRAL_REINTENTO
    assert puntaje_de_lectura(REVUELTA) < UMBRAL_REINTENTO


def test_el_monto_inverosimil_no_cuenta_como_buena_lectura():
    """Encontrar un monto que es un número de documento no es encontrarlo."""
    assert puntaje_de_lectura("Nit 890399003-4\nTotal 890399003\n") < UMBRAL_REINTENTO


def test_si_la_primera_lectura_es_buena_no_se_lee_dos_veces(monkeypatch):
    llamadas: list = []

    def espia(imagen, *args, **kwargs):
        llamadas.append(kwargs.get("config"))
        return BUENA

    monkeypatch.setattr(pytesseract, "image_to_string", espia)
    assert _mejor_lectura(Image.new("RGB", (60, 20), "white")) == BUENA
    assert len(llamadas) == 1, "no hay que gastar una segunda lectura si la primera sirve"


def test_si_la_primera_lectura_no_sirve_se_usa_la_segunda(monkeypatch):
    lecturas = iter([REVUELTA, BUENA])
    llamadas: list = []

    def espia(imagen, *args, **kwargs):
        llamadas.append(kwargs.get("config"))
        return next(lecturas)

    monkeypatch.setattr(pytesseract, "image_to_string", espia)
    assert _mejor_lectura(Image.new("RGB", (60, 20), "white")) == BUENA
    assert len(llamadas) == 2, "la segunda opinión tiene que pedirse"
    assert llamadas[0] == "--psm 4", "la primera lectura es la de una columna"


def test_si_las_dos_lecturas_son_malas_se_queda_la_primera(monkeypatch):
    """Ante dos lecturas malas no se cambia por cambiar: se conserva la primera."""
    lecturas = iter([REVUELTA, "Basura\n"])
    monkeypatch.setattr(pytesseract, "image_to_string", lambda *a, **k: next(lecturas))
    assert _mejor_lectura(Image.new("RGB", (60, 20), "white")) == REVUELTA
