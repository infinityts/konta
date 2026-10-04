"""El monto que teclea una persona se lee como **dinero**, no como un decimal inglés.

Pasó de verdad: al insertar un gasto de `65.928,09` la API respondía 422 («Input should be a
valid decimal») y la pantalla lo enseñaba como `[object Object]`, así que no había forma de
saber qué pasaba. El caso silencioso era peor: `65.928` se guardaba como **65,928 pesos**
cuando el usuario quería decir **65.928**.

La regla de la casa ya existía para las facturas y los extractos («una sola forma de leer
dinero», `dinero.parsear_monto`); lo que faltaba era aplicarla a lo que se teclea a mano.
"""

from __future__ import annotations

from test_api import _registrar

from app.recurrencia import hoy


def _gasto(client, h, monto, **extra):
    return client.post(
        "/transacciones",
        headers=h,
        json={
            "tipo": "gasto",
            "monto": monto,
            "fecha": hoy().isoformat(),
            "descripcion": "Compra Almohada Mariposa",
            **extra,
        },
    )


def test_el_monto_colombiano_se_guarda_bien(client):
    _, h = _registrar(client)
    for tecleado, esperado in [
        ("65.928,09", 65928.09),   # el caso que fallaba
        ("65,928.09", 65928.09),   # formato inglés
        ("$65.928,09", 65928.09),  # con el símbolo
        ("1.500.000", 1500000.0),  # solo puntos de miles
        ("65.928", 65928.0),       # ambiguo: en Colombia son pesos
        ("65928.09", 65928.09),    # ya en formato de máquina
        (65928.09, 65928.09),      # número, no texto
    ]:
        r = _gasto(client, h, tecleado)
        assert r.status_code == 201, f"{tecleado!r}: {r.text}"
        assert float(r.json()["monto"]) == esperado, f"{tecleado!r} -> {r.json()['monto']}"


def test_un_monto_que_no_se_entiende_lo_dice_claro(client):
    """Mejor un mensaje que se entienda que un `[object Object]` en pantalla."""
    _, h = _registrar(client)
    r = _gasto(client, h, "no es un monto")
    assert r.status_code == 422, r.text
    detalle = r.json()["detail"]
    assert isinstance(detalle, list), detalle
    assert "No se entiende el monto" in detalle[0]["msg"], detalle


def test_el_saldo_inicial_y_otros_importes_tambien(client):
    """Lo que se teclea en el resto de formularios se lee igual."""
    _, h = _registrar(client)
    r = client.post(
        "/cuentas",
        headers=h,
        json={"nombre": "Bancolombia", "tipo": "ahorro", "saldo_inicial": "1.234.567,89"},
    )
    assert r.status_code == 201, r.text
    assert float(r.json()["saldo_inicial"]) == 1234567.89

    r = client.post(
        "/suscripciones",
        headers=h,
        json={"nombre": "Streaming", "monto": "89.900,50", "periodicidad": "mensual"},
    )
    assert r.status_code == 201, r.text
    assert float(r.json()["monto"]) == 89900.50
