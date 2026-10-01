"""El freno a los intentos de contraseña.

Cinco fallos bloquean la cuenta diez minutos. El contador es **por correo** (protege a esa cuenta en
concreto) y **por IP** con un umbral más alto (frena a quien prueba muchos correos desde el mismo
sitio, sin dejar fuera a una oficina entera por los dedos de una persona).

Tres decisiones que importan:

- **El contador se borra al acertar** y el bloqueo **caduca solo**: no hay desbloqueos a mano.
- **El mensaje no dice si el correo existe** (eso sería regalar la mitad del trabajo) y **sí dice
  cuántos minutos faltan**, que es lo único que el usuario necesita saber.
- **Vive en la base**, no en memoria: un reinicio no puede borrar el bloqueo.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import IntentosLogin


def _ahora() -> datetime:
    return datetime.now(UTC)


def ip_del_cliente(peticion: Request) -> str | None:
    """La IP de quien pide, tal como la ve nginx.

    El backend está detrás de nginx, así que `request.client.host` es la IP **del proxy** para todo
    el mundo: sin esto, todos los usuarios compartirían un contador. nginx manda la real en
    `X-Real-IP`.
    """
    real = (peticion.headers.get("x-real-ip") or "").strip()
    if real:
        return real
    reenviadas = (peticion.headers.get("x-forwarded-for") or "").split(",")
    if reenviadas and reenviadas[0].strip():
        return reenviadas[0].strip()
    return peticion.client.host if peticion.client else None


def _claves(email: str, ip: str | None) -> list[tuple[str, int]]:
    ajustes = get_settings()
    claves = [(f"email:{email.lower()}", ajustes.login_intentos)]
    if ip and ajustes.login_intentos_ip > 0:
        claves.append((f"ip:{ip}", ajustes.login_intentos_ip))
    return claves


def _fila(db: Session, clave: str, bloquear: bool = False) -> IntentosLogin | None:
    consulta = select(IntentosLogin).where(IntentosLogin.clave == clave)
    if bloquear:
        consulta = consulta.with_for_update()
    return db.scalar(consulta)


def revisar(db: Session, email: str, ip: str | None) -> None:
    """Si está bloqueado, se dice cuánto falta (429) **antes** de mirar la contraseña."""
    ahora = _ahora()
    for clave, _limite in _claves(email, ip):
        fila = _fila(db, clave)
        if fila and fila.bloqueado_hasta and fila.bloqueado_hasta > ahora:
            faltan = max(1, int((fila.bloqueado_hasta - ahora).total_seconds() // 60) + 1)
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Demasiados intentos fallidos. Espera {faltan} minuto"
                    f"{'s' if faltan != 1 else ''} y vuelve a intentarlo."
                ),
            )


def anotar_fallo(db: Session, email: str, ip: str | None) -> None:
    """Suma un fallo y bloquea la clave que pase de su límite."""
    ajustes = get_settings()
    ahora = _ahora()
    ventana = timedelta(minutes=ajustes.login_ventana_minutos)
    for clave, limite in _claves(email, ip):
        fila = _fila(db, clave, bloquear=True)
        if fila is None:
            fila = IntentosLogin(clave=clave, intentos=0)
            db.add(fila)
        # Si el bloqueo anterior ya caducó, se empieza de cero
        if fila.bloqueado_hasta and fila.bloqueado_hasta <= ahora:
            fila.intentos, fila.bloqueado_hasta = 0, None
        # Y si pasó la ventana sin fallar, también (así un fallo suelto cada mucho no acumula)
        if (
            fila.actualizado_en
            and fila.actualizado_en < ahora - ventana
            and not fila.bloqueado_hasta
        ):
            fila.intentos = 0
        fila.intentos += 1
        fila.actualizado_en = ahora
        if limite > 0 and fila.intentos >= limite:
            fila.bloqueado_hasta = ahora + timedelta(minutes=ajustes.login_bloqueo_minutos)
    db.commit()


def anotar_exito(db: Session, email: str, ip: str | None) -> None:
    """Al acertar se borran los fallos **de esa cuenta** (la IP se deja, por si hay más gente)."""
    fila = _fila(db, f"email:{email.lower()}", bloquear=True)
    if fila is not None:
        fila.intentos, fila.bloqueado_hasta, fila.actualizado_en = 0, None, _ahora()
        db.commit()
