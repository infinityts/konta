"""Los montos que devuelve el modelo se leen con el mismo lector que usa el OCR.

Aquí hubo un bug de dinero real: `_decimal("45000.50")` daba 4.500.050 (cien veces más) y
`_monto(45000.5)` daba 450.005 (diez veces más). Son montos de acciones que el usuario confirma o de
facturas que se registran: un error de 10× o 100× es dinero mal apuntado.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _registrar

from app import ia, propuestas

# (lo que manda el modelo, lo que tiene que valer)
CASOS = [
    (45000, "45000"),
    ("45000", "45000"),
    ("45.000", "45000"),  # formato colombiano
    (45000.5, "45000.5"),
    ("45000.50", "45000.50"),
    ("1.234.567", "1234567"),
    ("$ 45.000,50", "45000.50"),
    ("45,000.50", "45000.50"),
]


def test_la_lectura_con_ia_lee_los_montos_como_el_resto_de_la_app():
    for entrada, esperado in CASOS:
        assert ia._decimal(entrada) == Decimal(esperado), f"{entrada!r} → {ia._decimal(entrada)}"


def test_la_lectura_con_ia_no_inventa_con_lo_que_no_es_un_monto():
    assert ia._decimal(None) is None
    assert ia._decimal("") is None
    assert ia._decimal("no sé") is None
    assert ia._decimal(True) is None, "un booleano no es un monto"


def test_las_propuestas_del_asistente_leen_los_montos_igual():
    for entrada, esperado in CASOS:
        assert propuestas._monto(entrada) == Decimal(esperado), f"{entrada!r} → {propuestas._monto(entrada)}"


def test_una_factura_leida_con_ia_guarda_el_monto_correcto(client, monkeypatch):
    """El camino completo: el modelo devuelve el monto como texto y la factura queda con el valor bueno."""
    from decimal import Decimal as D

    from app.ia import LecturaIa

    def falso(contenido, nombre, tipo, contrasena=None):
        return LecturaIa(
            texto="TOTAL $ 45.000,50\n",
            campos={"monto": "45,000.50", "fecha": "2026-09-30", "emisor": "X"},
            tokens_entrada=100,
            tokens_salida=20,
            costo_usd=D("0.0001"),
        )

    monkeypatch.setattr(ia, "leer_documento", falso)
    _, h = _registrar(client)
    from test_api import _pdf_minimo

    r = client.post(
        "/ia/leer",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo("Monto: $1\n"), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    assert Decimal(str(r.json()["monto_detectado"])) == Decimal("45000.50")
