"""Autenticación: registro y login (multi-usuario)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_db
from ..defaults import DEFAULT_CATEGORIAS
from ..models import Categoria, TipoCategoria, Usuario
from ..schemas import LoginIn, Token, UserCreate, UserOut
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: UserCreate, db: Session = Depends(get_db)) -> Usuario:
    if db.scalar(select(Usuario).where(Usuario.email == data.email)):
        raise HTTPException(status_code=409, detail="El email ya está registrado")

    usuario = Usuario(
        email=data.email,
        nombre=data.nombre,
        password_hash=hash_password(data.password),
        moneda_principal=data.moneda_principal,
    )
    db.add(usuario)
    db.flush()  # asigna usuario.id

    # Categorías por defecto para empezar con un tablero útil
    for cat in DEFAULT_CATEGORIAS:
        db.add(
            Categoria(
                usuario_id=usuario.id,
                nombre=cat["nombre"],
                tipo=TipoCategoria(cat["tipo"]),
                icono=cat["icono"],
                color=cat["color"],
            )
        )
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post("/login", response_model=Token)
def login(data: LoginIn, db: Session = Depends(get_db)) -> Token:
    usuario = db.scalar(select(Usuario).where(Usuario.email == data.email))
    if usuario is None or not verify_password(data.password, usuario.password_hash):
        raise HTTPException(status_code=401, detail="Email o contraseña incorrectos")
    return Token(access_token=create_access_token(usuario.id))
