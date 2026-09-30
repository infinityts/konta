"""El asistente: las cifras salen de las herramientas, no del modelo.

Es la prueba que importa: si el modelo «recordara» un saldo, todo lo demás sobra. Aquí se
comprueba que lo que recibe el modelo es **exactamente** lo que devuelve la API de la app, que
no puede ver datos de otro usuario, que el bucle está acotado y que el cupo se respeta.
"""

from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import text
from test_api import _registrar

from app import asistente, ia
from app.ia import ChatIa, LlamadaHerramienta


def _respuesta_con_herramienta(nombre: str, argumentos: dict | None = None) -> ChatIa:
    return ChatIa(
        texto="",
        llamadas=[LlamadaHerramienta(id="c1", nombre=nombre, argumentos=argumentos or {})],
        tokens_entrada=800,
        tokens_salida=60,
        costo_usd=Decimal("0.0003"),
    )


def test_las_cifras_que_recibe_el_modelo_son_las_de_la_app(client, monkeypatch):
    """El total que ve el modelo tiene que ser el mismo que el de la pantalla de cuentas."""
    _, h = _registrar(client)
    client.post(
        "/cuentas", headers=h, json={"nombre": "Bancolombia", "tipo": "ahorro", "saldo_inicial": "1500000"}
    )
    esperado = client.get("/cuentas", headers=h).json()["saldo_total"]

    vistos: list[list[dict]] = []

    def falso(mensajes, herramientas=None):
        vistos.append(mensajes)
        if len(vistos) == 1:
            return _respuesta_con_herramienta("cuentas")
        return ChatIa(texto="Tienes un total de 1.500.000.", tokens_entrada=700, tokens_salida=40)

    monkeypatch.setattr(ia, "chat", falso)
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "¿cuánto tengo?"})
    assert r.status_code == 200, r.text
    assert r.json()["herramientas_usadas"] == ["cuentas"]

    # lo que se le devolvió al modelo como resultado de la herramienta
    resultado = json.loads(vistos[1][-1]["content"])
    assert resultado["total"] == esperado, (resultado["total"], esperado)


def test_no_puede_ver_datos_de_otro_usuario(client, monkeypatch):
    """Cada pregunta lee con el usuario que la hace: dos usuarios, dos respuestas."""
    _, h_uno = _registrar(client, email="uno@example.com")
    _, h_dos = _registrar(client, email="dos@example.com")
    client.post(
        "/cuentas", headers=h_uno, json={"nombre": "Solo de uno", "tipo": "ahorro", "saldo_inicial": "999000"}
    )

    vistos: list[list[dict]] = []

    def falso(mensajes, herramientas=None):
        vistos.append(mensajes)
        if len(vistos) == 1:
            return _respuesta_con_herramienta("cuentas")
        return ChatIa(texto="No tienes cuentas.", tokens_entrada=100, tokens_salida=20)

    monkeypatch.setattr(ia, "chat", falso)
    r = client.post("/asistente/preguntar", headers=h_dos, json={"pregunta": "¿cuánto tengo?"})
    assert r.status_code == 200, r.text
    resultado = json.loads(vistos[1][-1]["content"])
    assert resultado["cuentas"] == []
    assert resultado["total"] == 0, "el asistente vio datos del otro usuario"


def test_el_bucle_esta_acotado_y_lo_dice(client, monkeypatch):
    """Un modelo que pide herramientas sin parar no puede quedarse dando vueltas."""
    _, h = _registrar(client)
    llamadas = []

    def insistente(mensajes, herramientas=None):
        llamadas.append(1)
        return _respuesta_con_herramienta("cuentas")

    monkeypatch.setattr(ia, "chat", insistente)
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "dame todo"})
    assert r.status_code == 200, r.text
    assert len(llamadas) == asistente.MAX_VUELTAS
    assert "más concreta" in r.json()["respuesta"]


def test_cuesta_una_consulta_y_se_agota(client, monkeypatch):
    _, h = _registrar(client)
    monkeypatch.setattr(ia, "chat", lambda m, herramientas=None: ChatIa(texto="Listo.", tokens_entrada=90, tokens_salida=10))
    antes = client.get("/ia/cuota", headers=h).json()["consultas_restantes"]
    assert client.post("/asistente/preguntar", headers=h, json={"pregunta": "hola"}).status_code == 200
    despues = client.get("/ia/cuota", headers=h).json()
    assert despues["consultas_restantes"] == antes - 1
    assert despues["tokens_entrada"] == 90

    # se agotan las 10 del plan Básico
    for _ in range(antes - 1):
        client.post("/asistente/preguntar", headers=h, json={"pregunta": "otra"})
    agotada = client.post("/asistente/preguntar", headers=h, json={"pregunta": "y otra"})
    assert agotada.status_code == 402, agotada.text
    assert "Se acabaron las consultas al asistente" in agotada.json()["detail"]


def test_sin_clave_el_asistente_esta_apagado_y_no_cobra(client):
    _, h = _registrar(client)
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "¿cómo voy?"})
    assert r.status_code == 503, r.text
    assert "no está configurado" in r.json()["detail"]
    assert client.get("/ia/cuota", headers=h).json()["consultas_usadas"] == 0


def test_el_manual_responde_con_pasos(client, monkeypatch):
    _, h = _registrar(client)
    assert "subir una factura o un recibo" in client.get("/asistente/manual", headers=h).json()["temas"]

    vistos: list[list[dict]] = []

    def falso(mensajes, herramientas=None):
        vistos.append(mensajes)
        if len(vistos) == 1:
            return _respuesta_con_herramienta("ayuda", {"tema": "subir una factura"})
        return ChatIa(texto="1. Entra en Facturas…", tokens_entrada=500, tokens_salida=80)

    monkeypatch.setattr(ia, "chat", falso)
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "¿cómo subo una factura?"})
    assert r.status_code == 200, r.text
    ayuda = json.loads(vistos[1][-1]["content"])
    primero = ayuda["resultados"][0]
    assert primero["tema"] == "subir una factura o un recibo"
    assert len(primero["pasos"]) >= 3


def test_una_herramienta_que_falla_no_tumba_la_respuesta(client, monkeypatch):
    _, h = _registrar(client)
    orden = []

    def falso(mensajes, herramientas=None):
        orden.append(1)
        if len(orden) == 1:
            return _respuesta_con_herramienta("no_existe")
        return ChatIa(texto="No pude consultarlo.", tokens_entrada=100, tokens_salida=20)

    monkeypatch.setattr(ia, "chat", falso)
    r = client.post("/asistente/preguntar", headers=h, json={"pregunta": "algo raro"})
    assert r.status_code == 200, r.text
    assert "no pude" in r.json()["respuesta"].lower()


def test_queda_registrado_para_el_informe(client, engine, monkeypatch):
    """La pregunta, las herramientas y el coste se guardan: con eso se sacan los promedios."""
    _, h = _registrar(client)
    monkeypatch.setattr(ia, "chat", lambda m, herramientas=None: ChatIa(texto="Ok.", tokens_entrada=120, tokens_salida=15, costo_usd=Decimal("0.0001")))
    client.post("/asistente/preguntar", headers=h, json={"pregunta": "¿cómo voy este mes?"})

    with engine.begin() as conn:
        fila = conn.execute(
            text("select pregunta, tokens_entrada, costo_usd from consultas_asistente")
        ).one()
    assert fila.pregunta == "¿cómo voy este mes?"
    assert fila.tokens_entrada == 120
