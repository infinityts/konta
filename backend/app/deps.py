"""Dependencias de FastAPI: sesión de BD y usuario autenticado."""

from __future__ import annotations

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .db import make_engine, make_session_factory
from .models import Usuario
from .security import decode_token

engine = make_engine()
SessionLocal = make_session_factory(engine)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """Resuelve el usuario a partir del Bearer token. Aísla los datos por usuario."""
    credenciales_invalidas = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o expiradas",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = decode_token(token)
    # `from None`: el motivo real del fallo del token no se le cuenta al cliente
    except Exception:  # noqa: BLE001 — cualquier fallo al decodificar el token es un 401; el motivo no se le cuenta al cliente
        raise credenciales_invalidas from None

    try:
        usuario = db.get(Usuario, uuid.UUID(user_id))
    except ValueError:
        raise credenciales_invalidas from None

    if usuario is None:
        raise credenciales_invalidas
    return usuario
