"""El freno a los intentos de contraseña.

Cinco fallos bloquean la cuenta diez minutos. Sin esto, nada impide probar contraseñas a lo bruto:
una lista de las mil más usadas contra un correo conocido es cuestión de minutos.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from test_api import _registrar

CLAVE = "password123"
# Cada test con su propia IP: el bloqueo por IP no tiene que mezclarse entre pruebas
IP = "198.51.100.9"


def _entrar(client, correo: str, clave: str = CLAVE, ip: str | None = None):
    cabeceras = {"X-Real-IP": ip} if ip else None
    return client.post("/auth/login", json={"email": correo, "password": clave}, headers=cabeceras)


def test_cinco_fallos_bloquean_la_cuenta_y_dicen_cuanto_falta(client):
    correo = "ana@example.com"
    _registrar(client, email=correo)

    for intento in range(4):
        assert _entrar(client, correo, "mala", ip=IP).status_code == 401, f"fallo {intento + 1}"
    assert _entrar(client, correo, "mala", ip=IP).status_code == 401  # el quinto bloquea

    bloqueado = _entrar(client, correo, "mala", ip=IP)
    assert bloqueado.status_code == 429, bloqueado.text
    detalle = bloqueado.json()["detail"]
    assert "minuto" in detalle, detalle
    assert "10" in detalle, f"tiene que decir cuánto falta: {detalle}"


def test_estando_bloqueado_no_entra_ni_con_la_contraseña_buena(client):
    """Si no, el bloqueo no serviría de nada: el que acierta a la sexta entra igual."""
    correo = "bruno@example.com"
    _registrar(client, email=correo)
    for _ in range(5):
        _entrar(client, correo, "mala", ip=IP)
    assert _entrar(client, correo, CLAVE, ip=IP).status_code == 429


def test_al_acertar_se_borran_los_fallos(client):
    correo = "carla@example.com"
    _registrar(client, email=correo)
    for _ in range(3):
        _entrar(client, correo, "mala", ip=IP)
    assert _entrar(client, correo, CLAVE, ip=IP).status_code == 200
    # otros tres fallos no bloquean: el contador se había borrado
    for _ in range(3):
        assert _entrar(client, correo, "mala", ip=IP).status_code == 401
    assert _entrar(client, correo, CLAVE, ip=IP).status_code == 200


def test_despues_del_bloqueo_se_puede_volver_a_intentar(client, engine):
    """El bloqueo caduca solo: nada de desbloqueos a mano."""
    from sqlalchemy import text

    correo = "diego@example.com"
    _registrar(client, email=correo)
    for _ in range(5):
        _entrar(client, correo, "mala", ip=IP)
    assert _entrar(client, correo, CLAVE, ip=IP).status_code == 429

    # se adelanta el reloj del bloqueo en vez de esperar diez minutos de verdad
    with engine.begin() as conn:
        conn.execute(
            text("update intentos_login set bloqueado_hasta = :antes where clave = :clave"),
            {"antes": datetime.now(UTC) - timedelta(seconds=1), "clave": f"email:{correo}"},
        )
    assert _entrar(client, correo, CLAVE, ip=IP).status_code == 200, "el bloqueo tenía que haber caducado"


def test_bloquear_una_cuenta_no_bloquea_a_las_demas(client):
    """El bloqueo es de la cuenta, no de todo el mundo (si no, sería un arma para dejar fuera a otros)."""
    _registrar(client, email="elena@example.com")
    _registrar(client, email="felipe@example.com")
    for _ in range(5):
        _entrar(client, "elena@example.com", "mala", ip=IP)
    assert _entrar(client, "elena@example.com", CLAVE, ip=IP).status_code == 429
    assert _entrar(client, "felipe@example.com", CLAVE, ip=IP).status_code == 200


def test_muchos_correos_distintos_desde_la_misma_ip_tambien_se_frenan(client):
    """El caso del que prueba mil correos desde el mismo sitio."""
    ips = "203.0.113.7"
    for numero in range(20):
        correo = f"prueba{numero}@example.com"
        _registrar(client, email=correo)
        assert _entrar(client, correo, "mala", ip=ips).status_code == 401

    correo = "otro@example.com"
    _registrar(client, email=correo)
    respuesta = _entrar(client, correo, CLAVE, ip=ips)
    assert respuesta.status_code == 429, "20 fallos desde la misma IP tienen que frenar"


def test_el_mensaje_no_revela_si_el_correo_existe(client):
    """Decir «ese correo no existe» es regalar la mitad del trabajo."""
    _registrar(client, email="gina@example.com")
    existente = _entrar(client, "gina@example.com", "mala", ip=IP)
    inexistente = _entrar(client, "no-existe@example.com", "mala", ip=IP)
    assert existente.status_code == inexistente.status_code == 401
    assert existente.json()["detail"] == inexistente.json()["detail"]
