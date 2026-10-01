"""La ayuda busca por significado, y si el Ollama no está, por palabras.

El CI no tiene Ollama, así que el embedder se sustituye por uno de mentira: lo que se prueba es la
lógica de la búsqueda (ordenar por parecido, descartar lo que no se parece y saber caer al plan B
cuando no hay embeddings).
"""

from __future__ import annotations

import pytest
from test_api import _registrar

from app import manual
from app.config import get_settings


@pytest.fixture(autouse=True)
def sin_indice_previo(monkeypatch):
    monkeypatch.setattr(get_settings(), "ollama_url", "http://ollama-de-mentira:11434")
    monkeypatch.setattr(get_settings(), "ayuda_similitud_minima", 0.45)
    monkeypatch.setattr(manual, "_CACHE", None)
    yield
    manual._CACHE = None


def _embedder_falso(
    mapa: dict[str, list[float]], resto: tuple[float, float, float] = (0.0, 1.0, 0.0)
):
    """Un embedder de mentira: reconoce pistas en el texto y da el vector de cada una.

    Lo que no reconoce recibe `resto`, **distinto** de los vectores del mapa: si todo recibiera el
    mismo vector, la similitud saldría 1 y el test no probaría nada.
    """

    def falso(texto: str, tipo: str = "documento"):
        for pista, vector in mapa.items():
            if pista.lower() in (texto or "").lower():
                return vector
        return list(resto)

    return falso


def test_ordena_por_significado_no_por_palabras(monkeypatch):
    # «plata que me queda» no comparte palabras con el tema, pero el vector los acerca
    monkeypatch.setattr(
        manual,
        "_embedder",
        lambda timeout=None: _embedder_falso(
            {
                "saber por qué mi saldo cambió": [1.0, 0.0, 0.0],
                "no me cuadra la plata que me queda": [0.99, 0.01, 0.0],
                "hacer un presupuesto": [0.0, 1.0, 0.0],
            },
            resto=(0.0, 0.0, 1.0),
        ),
    )
    resultado = manual.buscar("no me cuadra la plata que me queda")
    assert resultado["como"] == "significado"
    assert resultado["resultados"][0]["tema"] == "saber por qué mi saldo cambió"
    assert resultado["resultados"][0]["similitud"] > 0.9
    # el umbral es un piso: nada por debajo entra en los candidatos
    assert all(
        r["similitud"] >= get_settings().ayuda_similitud_minima for r in resultado["resultados"]
    )
    assert "aviso" in resultado, "el modelo tiene que saber que la puntuación no decide"


def test_si_nada_se_parece_lo_suficiente_lo_dice(monkeypatch):
    """Mejor decir «no lo tengo» que inventarse los pasos."""
    monkeypatch.setattr(
        manual,
        "_embedder",
        lambda timeout=None: _embedder_falso({"otra consulta": [0.0, 0.0, 1.0]}, resto=(0.0, 1.0, 0.0)),
    )
    resultado = manual.buscar("otra consulta")
    assert resultado["resultados"] == []
    assert "no lo tienes" in resultado["nota"]


def test_si_no_hay_ollama_configurado_se_busca_por_palabras(monkeypatch):
    """La ayuda no puede depender de que el Ollama esté vivo."""
    monkeypatch.setattr(get_settings(), "ollama_url", None)
    resultado = manual.buscar("presupuesto")
    assert resultado["como"] == "palabras"
    assert any("presupuesto" in r["tema"] for r in resultado["resultados"])


def test_si_el_indice_queda_vacio_tambien_cae_a_palabras(monkeypatch):
    """Un embedder que no devuelve nada no puede dejar al usuario sin respuesta."""
    monkeypatch.setattr(manual, "_embedder", lambda timeout=None: (lambda texto, tipo="documento": None))
    resultado = manual.buscar("presupuesto")
    assert resultado["como"] == "palabras"
    assert resultado["resultados"]


def test_la_busqueda_por_palabras_dice_cuando_no_encuentra(monkeypatch):
    monkeypatch.setattr(get_settings(), "ollama_url", None)
    resultado = manual.buscar("xyzzy plugh")
    assert resultado["resultados"] == []
    assert "nota" in resultado


def test_el_manual_nombra_las_pantallas_de_verdad(client):
    """Quien pregunta está mirando la app: los pasos tienen que decir la pantalla como se llama."""
    assert len(manual.temas()) >= 20
    texto = " ".join(" ".join(p) for p in manual.TEMAS.values())
    for pantalla in ("Transacciones", "Cuentas", "Facturas", "Presupuestos", "Reportes", "Metas",
                     "Etiquetas", "Respaldo", "Asistente", "Gastos recurrentes"):
        assert pantalla in texto, f"el manual no menciona {pantalla}"


def test_el_endpoint_de_busqueda_responde(client, monkeypatch):
    _, h = _registrar(client)
    monkeypatch.setattr(get_settings(), "ollama_url", None)
    r = client.get("/asistente/buscar?q=presupuesto", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["resultados"]
    assert client.get("/asistente/manual", headers=h).json()["cuantos"] >= 20


def test_el_manual_cubre_las_cosas_que_la_app_sabe_hacer(client):
    """Un hueco real: la app soporta transferencias entre cuentas y el manual no las explicaba.

    El asistente dijo la verdad («no tengo ese tema»), que es justo lo que se le pide; el fallo era
    del manual, no suyo. Aquí se fija que los temas que la app sí sabe hacer estén.
    """
    temas = manual.temas()
    for imprescindible in (
        "transferir dinero entre mis cuentas",
        "crear una cuenta y poner su saldo inicial",
        "corregir o borrar un movimiento",
        "el IVA de mis facturas",
    ):
        assert imprescindible in temas, f"el manual no explica: {imprescindible}"

    # y el de transferencias dice lo que de verdad hace la app (origen, destino y que el total no cambia)
    pasos = " ".join(manual.TEMAS["transferir dinero entre mis cuentas"])
    assert "origen" in pasos and "destino" in pasos
    assert "no cambia" in pasos, "hay que decir que el total de tu dinero no cambia"
    assert "tarjeta" in pasos, "y cómo se paga una tarjeta"
