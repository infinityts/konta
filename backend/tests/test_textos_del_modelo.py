"""Lo que devuelve el modelo entra por **un solo sitio**, y ahí se acota.

Este archivo nació de un test mal hecho: yo sustituía `leer_documento` y luego le exigía al endpoint
que protegiera los textos largos. Pero sustituir esa función **también sustituye sus garantías**, y
la función de verdad ya acorta todo a lo que aguantan las columnas y descarta lo que no sirve.

Así que aquí se prueba la garantía de verdad: se sustituye solo la llamada al proveedor (el HTTP) y
se comprueba que `leer_documento` acota los textos y descarta las líneas que no valen.
"""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest

from app import ia


class _RespuestaFalsa:
    def __init__(self, cuerpo: dict):
        self._cuerpo = cuerpo

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._cuerpo


def _proveedor(monkeypatch, contenido: dict):
    """Sustituye la llamada HTTP: lo que hace el modelo de verdad, pero sin red ni dinero."""
    cuerpo = {
        "choices": [{"message": {"content": json.dumps(contenido)}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
    }

    class _Cliente:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_, **__):
            return False

        def post(self, *_, **__):
            return _RespuestaFalsa(cuerpo)

    monkeypatch.setattr(ia.httpx, "Client", _Cliente)
    monkeypatch.setattr(ia, "configurada", lambda: True)


def test_los_textos_largos_se_acortan_a_lo_que_aguantan_las_columnas(monkeypatch):
    """`emisor_nombre` es de 140 y la descripción de la línea, de 255."""
    _proveedor(
        monkeypatch,
        {
            "texto": "T" * 40000,
            "monto": "45.000",
            "fecha": "2026-09-30",
            "emisor": "A" * 300,
            "nit": "9" * 80,
            "lineas": [{"descripcion": "B" * 400, "valor": 1000}],
        },
    )
    lectura = ia.leer_documento(b"png-de-mentira", "f.png", "image/png")

    assert len(lectura.texto) == 20000
    assert len(lectura.campos["emisor"]) == 140
    assert len(lectura.campos["nit"]) == 40
    assert len(lectura.campos["lineas"][0]["descripcion"]) == 200
    # y el monto se lee bien, no como texto crudo
    assert lectura.campos["monto"] == Decimal("45000")


def test_las_lineas_que_no_sirven_se_descartan_en_vez_de_guardarse(monkeypatch):
    """Una línea sin descripción, sin valor o con valor cero no es un artículo."""
    _proveedor(
        monkeypatch,
        {
            "texto": "TOTAL 1.000\n",
            "monto": 1000,
            "lineas": [
                {"descripcion": "BUENA", "valor": 500},
                {"descripcion": "", "valor": 500},
                {"descripcion": "SIN VALOR"},
                {"descripcion": "VALOR CERO", "valor": 0},
                {"descripcion": "VALOR MALO", "valor": "no es un número"},
                "esto no es un objeto",
            ],
        },
    )
    lectura = ia.leer_documento(b"png-de-mentira", "f.png", "image/png")
    assert [linea["descripcion"] for linea in lectura.campos["lineas"]] == ["BUENA"]


def test_un_monto_con_decimales_se_lee_bien(monkeypatch):
    """La familia del dinero: `"45,000.50"` no puede convertirse en 4.500.050."""
    _proveedor(monkeypatch, {"texto": "x", "monto": "45,000.50"})
    lectura = ia.leer_documento(b"png-de-mentira", "f.png", "image/png")
    assert lectura.campos["monto"] == Decimal("45000.50")


def test_si_el_proveedor_no_responde_se_dice_y_no_se_inventa(monkeypatch):
    class _ClienteRoto:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_, **__):
            return False

        def post(self, *_, **__):
            raise httpx.ConnectError("sin red")

    monkeypatch.setattr(ia.httpx, "Client", _ClienteRoto)
    monkeypatch.setattr(ia, "configurada", lambda: True)
    with pytest.raises(httpx.ConnectError):  # el endpoint lo convierte en 502 y no cobra
        ia.leer_documento(b"png-de-mentira", "f.png", "image/png")
