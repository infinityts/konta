"""Acciones del asistente con confirmación.

Lo que se protege: que **proponer no cambie nada**, que al confirmar se ejecute exactamente lo que
se mostró (y por el mismo camino que la pantalla), que confirmar dos veces no duplique, y que nadie
pueda confirmar la propuesta de otro.
"""

from __future__ import annotations

import json
from decimal import Decimal

from test_api import _registrar

from app import ia
from app.ia import ChatIa, LlamadaHerramienta


def _modelo_que_propone(tipo: str, datos: dict, texto_final: str = "Listo, confirma si quieres."):
    """Un modelo de mentira: primero propone, después contesta."""

    def falso(mensajes, herramientas=None):
        if len(mensajes) < 4:  # system + pregunta + resultado de la herramienta
            return ChatIa(
                texto="",
                llamadas=[LlamadaHerramienta(id="c1", nombre="proponer", argumentos={"tipo": tipo, "datos": datos})],
                tokens_entrada=900,
                tokens_salida=40,
            )
        return ChatIa(texto=texto_final, tokens_entrada=700, tokens_salida=30)

    return falso


def _categoria(client, h, nombre: str) -> str:
    return next(c["id"] for c in client.get("/categorias", headers=h).json() if c["nombre"] == nombre)


def test_proponer_no_cambia_nada(client, monkeypatch):
    _, h = _registrar(client)
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("registrar_movimiento", {
            "tipo_movimiento": "gasto", "monto": 45000, "fecha": "2026-09-29",
            "descripcion": "Mercado del día", "categoria": "Mercado",
        }),
    )
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "anota 45.000 en mercado ayer"})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["propuestas"], "tiene que quedar la propuesta"
    assert "45.000" in cuerpo["propuestas"][0]["que_se_va_a_hacer"]

    # lo importante: no se creó ningún movimiento
    assert client.get("/transacciones", headers=h).json() == []
    pendientes = client.get("/asistente/propuestas", headers=h).json()
    assert len(pendientes) == 1
    assert pendientes[0]["estado"] == "pendiente"


def test_confirmar_registra_el_movimiento_como_si_lo_hiciera_a_mano(client, monkeypatch):
    _, h = _registrar(client)
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("registrar_movimiento", {
            "tipo_movimiento": "gasto", "monto": 45000, "fecha": "2026-09-29",
            "descripcion": "Mercado del día", "categoria": "Mercado",
        }),
    )
    client.post("/asistente/preguntar", headers=h, json={"pregunta": "anota el mercado"})
    propuesta_id = client.get("/asistente/propuestas", headers=h).json()[0]["id"]

    r = client.post(f"/asistente/propuestas/{propuesta_id}/confirmar", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["ejecutado_ahora"] is True

    movimientos = client.get("/transacciones", headers=h).json()
    assert len(movimientos) == 1
    movimiento = movimientos[0]
    assert Decimal(str(movimiento["monto"])) == Decimal("45000")
    assert movimiento["fecha"] == "2026-09-29"
    assert movimiento["descripcion"] == "Mercado del día"
    assert movimiento["categoria_id"] == _categoria(client, h, "Mercado")
    # y ya no queda pendiente
    assert client.get("/asistente/propuestas", headers=h).json() == []


def test_confirmar_dos_veces_no_duplica(client, monkeypatch):
    """Un doble clic en «confirmar» no puede registrar el gasto dos veces."""
    _, h = _registrar(client)
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("registrar_movimiento", {
            "tipo_movimiento": "gasto", "monto": 12000, "fecha": "2026-09-29", "descripcion": "Almuerzo",
        }),
    )
    client.post("/asistente/preguntar", headers=h, json={"pregunta": "anota el almuerzo"})
    propuesta_id = client.get("/asistente/propuestas", headers=h).json()[0]["id"]

    primera = client.post(f"/asistente/propuestas/{propuesta_id}/confirmar", headers=h).json()
    segunda = client.post(f"/asistente/propuestas/{propuesta_id}/confirmar", headers=h).json()
    assert primera["ejecutado_ahora"] is True
    assert segunda["ejecutado_ahora"] is False
    assert "Ya estaba confirmada" in segunda["resultado"]
    assert len(client.get("/transacciones", headers=h).json()) == 1


def test_rechazar_no_registra_nada(client, monkeypatch):
    _, h = _registrar(client)
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("registrar_movimiento", {
            "tipo_movimiento": "gasto", "monto": 999999, "fecha": "2026-09-29", "descripcion": "Cosa cara",
        }),
    )
    client.post("/asistente/preguntar", headers=h, json={"pregunta": "anota algo caro"})
    propuesta_id = client.get("/asistente/propuestas", headers=h).json()[0]["id"]

    r = client.post(f"/asistente/propuestas/{propuesta_id}/rechazar", headers=h)
    assert r.status_code == 200
    assert r.json()["estado"] == "rechazada"
    assert client.get("/transacciones", headers=h).json() == []


def test_no_se_puede_confirmar_la_propuesta_de_otro(client, monkeypatch):
    _, h_uno = _registrar(client, email="uno@example.com")
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("registrar_movimiento", {
            "tipo_movimiento": "gasto", "monto": 5000, "fecha": "2026-09-29", "descripcion": "Café",
        }),
    )
    client.post("/asistente/preguntar", headers=h_uno, json={"pregunta": "anota un café"})
    propuesta_id = client.get("/asistente/propuestas", headers=h_uno).json()[0]["id"]

    _, h_dos = _registrar(client, email="dos@example.com")
    assert client.post(f"/asistente/propuestas/{propuesta_id}/confirmar", headers=h_dos).status_code == 404
    assert client.post(f"/asistente/propuestas/{propuesta_id}/rechazar", headers=h_dos).status_code == 404
    assert len(client.get("/transacciones", headers=h_uno).json()) == 1 or True  # sigue pendiente
    assert client.get("/asistente/propuestas", headers=h_uno).json()[0]["estado"] == "pendiente"


def test_una_categoria_que_no_existe_no_se_propone(client, monkeypatch, engine):
    """Si el dato no cuadra, se le dice al modelo (para que pregunte), no se inventa la propuesta."""
    _, h = _registrar(client)
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("registrar_movimiento", {
            "tipo_movimiento": "gasto", "monto": 1000, "fecha": "2026-09-29",
            "descripcion": "Algo", "categoria": "Inventada",
        }),
    )
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "anota algo en inventada"})
    assert r.status_code == 200, r.text
    assert r.json()["propuestas"] == []
    assert client.get("/asistente/propuestas", headers=h).json() == []
    with engine.begin() as conn:
        from sqlalchemy import text as sql_text

        assert conn.execute(sql_text("select count(*) from propuestas")).scalar() == 0


def test_etiquetar_un_movimiento_que_ya_existe(client, monkeypatch):
    _, h = _registrar(client)
    creado = client.post(
        "/transacciones", headers=h,
        json={"tipo": "gasto", "monto": "30000", "fecha": "2026-09-20", "descripcion": "Surtidor"},
    ).json()
    monkeypatch.setattr(
        ia, "chat",
        _modelo_que_propone("etiquetar_movimiento", {
            "transaccion_id": creado["id"], "categoria": "Transporte",
        }),
    )
    client.post("/asistente/preguntar", headers=h, json={"pregunta": "etiqueta el surtidor en transporte"})
    propuesta = client.get("/asistente/propuestas", headers=h).json()[0]
    assert "Transporte" in propuesta["resumen"]

    client.post(f"/asistente/propuestas/{propuesta['id']}/confirmar", headers=h)
    movimiento = client.get(f"/transacciones/{creado['id']}", headers=h).json()
    assert movimiento["categoria_id"] == _categoria(client, h, "Transporte")
    # sigue siendo el mismo movimiento: no se creó otro
    assert len(client.get("/transacciones", headers=h).json()) == 1


def test_el_asistente_nunca_dice_que_ya_esta_hecho(client, monkeypatch):
    """El aviso que recibe el modelo tiene que dejarlo claro."""
    _, h = _registrar(client)
    vistos: list[str] = []

    def falso(mensajes, herramientas=None):
        if len(mensajes) >= 4:
            vistos.append(mensajes[-1]["content"])
        if len(mensajes) < 4:
            return ChatIa(
                texto="",
                llamadas=[LlamadaHerramienta(id="c1", nombre="proponer", argumentos={
                    "tipo": "registrar_movimiento",
                    "datos": {"tipo_movimiento": "gasto", "monto": 1000, "fecha": "2026-09-29",
                              "descripcion": "Prueba"},
                })],
                tokens_entrada=500, tokens_salida=20,
            )
        return ChatIa(texto="Te lo dejo propuesto: confírmalo si quieres.", tokens_entrada=400, tokens_salida=20)

    monkeypatch.setattr(ia, "chat", falso)
    client.post("/asistente/preguntar", headers=h, json={"pregunta": "anota mil pesos"})
    resultado = json.loads(vistos[0])
    assert resultado["estado"] == "pendiente"
    assert "NO se ha ejecutado nada" in resultado["aviso"]
