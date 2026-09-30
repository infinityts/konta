"""Cuotas de la IA: el límite por plan, el saldo comprado y el coste real.

Lo que decide si un plan deja ganancia no es cuántas lecturas hizo el usuario, sino cuántos
tokens costaron. Por eso el consumo guarda las dos cosas.
"""

from __future__ import annotations

import os
from decimal import Decimal

import psycopg
from test_api import _pdf_minimo, _registrar

from app import cuotas, ia
from app.ia import LecturaIa


def _dar_lecturas_extra(email: str, cuantas: int) -> None:
    """Simula el saldo comprado (la pasarela de pago es otra tarea)."""
    url = os.environ["FINANZAS_TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as con:
        con.execute("update usuarios set lecturas_extra = %s where email = %s", (cuantas, email))
        con.commit()


def _stub(monkeypatch, monto="46477", tokens=(1500, 400), costo="0.0007") -> None:
    def falso(contenido, nombre, tipo, contrasena=None):
        return LecturaIa(
            texto="Gases de Occidente S.A. ESP\nMonto: $46.477\nFecha: 30/09/2026\n",
            campos={
                "monto": Decimal(monto),
                "fecha": "2026-09-30",
                "emisor": "Gases de Occidente",
                "nit": "800167643-5",
                "lineas": [],
            },
            tokens_entrada=tokens[0],
            tokens_salida=tokens[1],
            costo_usd=Decimal(costo),
        )

    monkeypatch.setattr(ia, "leer_documento", falso)


def _leer(client, h):
    return client.post(
        "/ia/leer",
        headers=h,
        files={"archivo": ("recibo.png", b"\x89PNG\r\n\x1a\n datos", "image/png")},
    )


def test_el_catalogo_de_planes_es_datos_no_codigo(client):
    _, h = _registrar(client)
    planes = client.get("/ia/planes", headers=h).json()
    codigos = [p["codigo"] for p in planes]
    assert codigos == ["basico", "personal", "pro"], codigos
    basico = planes[0]
    assert basico["precio_mes"] == "6000.00"
    assert basico["lecturas_ia"] == 10


def test_la_cuota_empieza_llena_y_baja_con_cada_lectura(client, monkeypatch):
    _, h = _registrar(client)
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["plan"] == "basico"
    assert cuota["lecturas_restantes"] == 10
    assert cuota["costo_usd"] == 0.0

    _stub(monkeypatch)
    detalle = _leer(client, h)
    assert detalle.status_code == 201, detalle.text
    # la lectura entra como una factura normal, con su texto y su monto
    assert detalle.json()["monto_detectado"] == "46477.00"

    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["lecturas_usadas"] == 1
    assert cuota["lecturas_restantes"] == 9
    # y quedó el gasto real, que es lo que vigila el margen
    assert cuota["tokens_entrada"] == 1500
    assert cuota["tokens_salida"] == 400
    assert cuota["costo_usd"] == 0.0007


def test_al_agotar_el_plan_se_explica_y_no_se_gasta(client, monkeypatch):
    email, h = _registrar(client)
    _stub(monkeypatch)
    for _ in range(10):
        assert _leer(client, h).status_code == 201

    agotada = _leer(client, h)
    assert agotada.status_code == 402, agotada.text
    assert "Se acabaron las lecturas con IA" in agotada.json()["detail"]
    assert "la lectura normal de Konta sigue funcionando" in agotada.json()["detail"]
    # y no se llamó al proveedor: el cupo se comprueba antes
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["lecturas_usadas"] == 10

    # con saldo comprado, sigue leyendo
    _dar_lecturas_extra(email, 3)
    assert _leer(client, h).status_code == 201
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["lecturas_extra"] == 2  # el saldo se gasta después de lo incluido


def test_sin_clave_la_funcion_esta_apagada_y_no_cobra(client):
    _, h = _registrar(client)
    respuesta = _leer(client, h)
    assert respuesta.status_code == 503, respuesta.text
    assert "no está configurada" in respuesta.json()["detail"]
    # apagada no es rota: no consume cupo
    assert client.get("/ia/cuota", headers=h).json()["lecturas_usadas"] == 0


def test_un_fallo_del_proveedor_no_se_cobra(client, monkeypatch):
    _, h = _registrar(client)

    def falla(*_a, **_k):
        raise RuntimeError("el proveedor se cayó")

    monkeypatch.setattr(ia, "leer_documento", falla)
    respuesta = _leer(client, h)
    assert respuesta.status_code == 502, respuesta.text
    assert "no se descontó ninguna lectura" in respuesta.json()["detail"]
    assert client.get("/ia/cuota", headers=h).json()["lecturas_usadas"] == 0


def test_la_cuota_es_por_mes(client):
    """El mes que viene vuelve a estar lleno, sin tocar nada."""
    _, h = _registrar(client)
    assert cuotas.periodo_actual() == cuotas.hoy().strftime("%Y-%m")
    assert client.get("/ia/cuota", headers=h).json()["periodo"] == cuotas.periodo_actual()


def test_el_costo_se_calcula_con_los_precios_del_momento(client):
    """1.500 de entrada y 400 de salida a 0,30 y 1,20 por millón."""
    costo = cuotas.costo_de_lectura(1500, 400, 0.30, 1.20)
    assert costo == Decimal("0.00093")


def test_la_contrasena_del_pdf_llega_al_adaptador(client, monkeypatch):
    """Las facturas electrónicas vienen protegidas: la clave tiene que llegar hasta el PDF."""
    _, h = _registrar(client)
    vistas = []

    def espia(contenido, nombre, tipo, contrasena=None):
        vistas.append(contrasena)
        return LecturaIa(texto="Monto: $1.000\n", campos={"monto": Decimal("1000")})

    monkeypatch.setattr(ia, "leer_documento", espia)
    client.post(
        "/ia/leer",
        headers=h,
        files={"archivo": ("f.pdf", b"%PDF-1.4", "application/pdf")},
        data={"contrasena": "900123456"},
    )
    assert vistas == ["900123456"]


def test_el_pdf_se_convierte_en_imagen_para_el_modelo(client):
    """El proveedor solo acepta imágenes: un PDF se convierte (misma tubería que el OCR)."""
    mime, _datos = ia._a_imagen(_pdf_minimo("Monto: $46.477\n"), "application/pdf")
    assert mime == "image/jpeg"
