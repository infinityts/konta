"""El freno de uso en lo que cuesta dinero.

Cada consulta al asistente y cada lectura con IA las pagamos nosotros. Esto no es el tope del plan
(eso lo pone la cuota): es un freno a ir muy rápido, y **frena antes** de tocar la cuota, para que
pasarse de rápido no le gaste la consulta del plan al cliente.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from test_api import _pdf_minimo, _registrar

from app.config import get_settings

# Los límites se leen de los ajustes, no se copian: si se afinan, estos tests siguen valiendo
CONSULTAS = get_settings().limite_consultas_por_minuto
LECTURAS = get_settings().limite_lecturas_por_minuto


def _cuota(client, h) -> dict:
    return client.get("/ia/cuota", headers=h).json()


def test_una_rafaga_de_consultas_se_frena_sin_gastar_el_plan(client):
    """10 consultas en un minuto pasan; la 11 se frena y **no** gasta cupo."""
    _, h = _registrar(client)
    # Sin clave de IA cada consulta responde 503: lo que se prueba aquí es el **freno**, no el modelo
    for numero in range(CONSULTAS):
        r = client.post("/asistente/preguntar", headers=h, json={"pregunta": f"pregunta {numero}"})
        assert r.status_code != 429, f"la {numero + 1} no debería estar frenada: {r.text[:120]}"

    usadas_antes = _cuota(client, h)["consultas_usadas"]
    frenada = client.post("/asistente/preguntar", headers=h, json={"pregunta": "otra más"})
    assert frenada.status_code == 429, frenada.text
    detalle = frenada.json()["detail"]
    assert "segundo" in detalle and "No se descontó nada de tu plan" in detalle, detalle
    assert _cuota(client, h)["consultas_usadas"] == usadas_antes, "frenar no puede gastar cupo"


def test_la_ventana_se_reinicia_sola(client, engine):
    """Al pasar el minuto se puede volver a preguntar, sin desbloquear nada a mano."""
    from sqlalchemy import text

    _, h = _registrar(client)
    for numero in range(CONSULTAS + 1):
        client.post("/asistente/preguntar", headers=h, json={"pregunta": f"pregunta {numero}"})
    assert client.post("/asistente/preguntar", headers=h, json={"pregunta": "frenada"}).status_code == 429

    # se adelanta la ventana en vez de esperar un minuto de verdad
    with engine.begin() as conn:
        conn.execute(
            text("update limites_uso set ventana_inicio = :antes where clave like '%consultas'"),
            {"antes": datetime.now(UTC) - timedelta(seconds=61)},
        )
    respuesta = client.post("/asistente/preguntar", headers=h, json={"pregunta": "después"})
    assert respuesta.status_code != 429, "la ventana tenía que haberse reiniciado"


def test_una_rafaga_de_lecturas_con_ia_se_frena(client):
    """Las lecturas por minuto que digan los ajustes: la siguiente se frena (sin gastar el plan)."""
    _, h = _registrar(client)
    for numero in range(LECTURAS):
        r = client.post(
            "/ia/leer",
            headers=h,
            files={"archivo": ("f.pdf", _pdf_minimo(f"Monto: $1.000\n{numero}\n"), "application/pdf")},
        )
        assert r.status_code != 429, f"la lectura {numero + 1} no debería estar frenada: {r.text[:120]}"

    restantes_antes = _cuota(client, h)["lecturas_restantes"]
    frenada = client.post(
        "/ia/leer",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo("Monto: $2.000\n"), "application/pdf")},
    )
    assert frenada.status_code == 429, frenada.text
    assert _cuota(client, h)["lecturas_restantes"] == restantes_antes


def test_crear_cuentas_en_serie_se_frena_por_ip(client):
    """El hueco de verdad: cada cuenta nueva trae plan gratis que pagamos nosotros."""
    for numero in range(5):
        r = client.post(
            "/auth/register",
            json={"email": f"serie{numero}@example.com", "nombre": "Serie", "password": "password123"},
            headers={"X-Real-IP": "198.51.100.50"},
        )
        assert r.status_code == 201, f"la cuenta {numero + 1} no debería estar frenada: {r.text[:120]}"

    sexta = client.post(
        "/auth/register",
        json={"email": "serie5@example.com", "nombre": "Serie", "password": "password123"},
        headers={"X-Real-IP": "198.51.100.50"},
    )
    assert sexta.status_code == 429, sexta.text
    assert "crear cuentas" in sexta.json()["detail"]

    # desde otra IP sí se puede: el freno es de quien abusa, no de todo el mundo
    otra = client.post(
        "/auth/register",
        json={"email": "otra-ip@example.com", "nombre": "Otra", "password": "password123"},
        headers={"X-Real-IP": "198.51.100.51"},
    )
    assert otra.status_code == 201, otra.text


def test_el_uso_normal_no_se_frena(client):
    """Tres consultas seguidas y dos lecturas: lo normal de una persona, sin frenos."""
    _, h = _registrar(client)
    for numero in range(3):
        assert client.post("/asistente/preguntar", headers=h, json={"pregunta": f"normal {numero}"}).status_code != 429
    for numero in range(2):
        assert (
            client.post(
                "/ia/leer",
                headers=h,
                files={"archivo": ("f.pdf", _pdf_minimo(f"Monto: $3.000\n{numero}\n"), "application/pdf")},
            ).status_code
            != 429
        )
