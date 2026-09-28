"""Configuración y prueba de notificaciones (Telegram / email)."""

from __future__ import annotations

import json
import urllib.request

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..alertas import calcular_alertas
from ..config import get_settings
from ..deps import get_current_user, get_db
from ..models import Usuario
from ..notificaciones import enviar, obtener_o_crear
from ..recurrencia import hoy
from ..schemas import (
    DetectarTelegramOut,
    NotificacionesIn,
    NotificacionesOut,
    PruebaNotificacionOut,
)

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


@router.get("", response_model=NotificacionesOut)
def obtener(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return obtener_o_crear(db, user)


@router.put("", response_model=NotificacionesOut)
def actualizar(
    data: NotificacionesIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    config = obtener_o_crear(db, user)
    for campo, valor in data.model_dump().items():
        setattr(config, campo, valor)
    db.commit()
    db.refresh(config)
    return config


@router.post("/probar", response_model=PruebaNotificacionOut)
def probar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Envía una notificación de prueba por los canales configurados."""
    config = obtener_o_crear(db, user)
    alertas = calcular_alertas(db, user.id, config.dias_anticipacion)
    if not alertas:
        alertas = [
            {
                "tipo": "prueba",
                "titulo": "Notificación de prueba de Konta",
                "fecha": hoy(),
                "dias_restantes": 0,
                "monto": None,
                "moneda": None,
            }
        ]
    try:
        enviados = enviar(config, alertas)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"enviados": enviados, "alertas": len(alertas)}


@router.post("/telegram/detectar", response_model=DetectarTelegramOut)
def detectar_telegram(user: Usuario = Depends(get_current_user)):
    """Lee los chats que le escribieron al bot, para sacar el chat ID."""
    token = get_settings().telegram_bot_token
    if not token:
        raise HTTPException(status_code=400, detail="Falta configurar FINANZAS_TELEGRAM_BOT_TOKEN en el servidor")

    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"No se pudo consultar Telegram: {exc}"
        ) from exc

    chats: dict[str, str] = {}
    for upd in data.get("result", []):
        mensaje = upd.get("message") or upd.get("edited_message") or upd.get("channel_post") or {}
        chat = mensaje.get("chat") or {}
        if chat.get("id"):
            nombre = (
                chat.get("title")
                or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
                or chat.get("username")
                or ""
            )
            chats[str(chat["id"])] = nombre

    return {"chats": [{"chat_id": k, "nombre": v} for k, v in chats.items()]}
