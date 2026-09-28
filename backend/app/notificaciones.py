"""Envío de notificaciones de alarmas de pago (Telegram, correo y WhatsApp).

La configuración de servidor (token del bot, SMTP y Cloud API de Meta) es global;
cada usuario elige canal, destino y días de anticipación.
"""

from __future__ import annotations

import json
import smtplib
import urllib.parse
import urllib.request
from email.message import EmailMessage

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from .alertas import calcular_alertas
from .config import get_settings
from .db import make_engine, make_session_factory
from .models import ConfigNotificaciones
from .recurrencia import hoy

ASUNTO = "Konta — pagos próximos"


def construir_mensaje(alertas: list[dict]) -> str:
    lineas = ["🔔 Konta — pagos próximos", ""]
    for a in alertas:
        dias = a["dias_restantes"]
        cuando = "hoy" if dias == 0 else ("¡vencido!" if dias < 0 else f"en {dias} día(s)")
        monto = f" — {a['monto']} {a.get('moneda') or ''}".rstrip() if a.get("monto") is not None else ""
        lineas.append(f"• {a['fecha']} ({cuando}): {a['titulo']}{monto}")
    lineas.append("")
    lineas.append(f"{len(alertas)} pago(s) próximo(s).")
    return "\n".join(lineas)


def enviar_telegram(chat_id: str, texto: str) -> None:
    token = get_settings().telegram_bot_token
    if not token:
        raise RuntimeError("Falta configurar FINANZAS_TELEGRAM_BOT_TOKEN en el servidor")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    datos = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode()
    try:
        with urllib.request.urlopen(url, data=datos, timeout=15) as resp:  # noqa: S310
            cuerpo = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"No se pudo hablar con Telegram: {exc}") from exc
    if not cuerpo.get("ok"):
        raise RuntimeError(f"Telegram respondió: {cuerpo.get('description')}")


def enviar_email(destino: str, texto: str) -> None:
    s = get_settings()
    if not s.smtp_host:
        raise RuntimeError("Falta configurar FINANZAS_SMTP_HOST en el servidor")
    msg = EmailMessage()
    msg["From"] = s.smtp_from or s.smtp_user or "konta@localhost"
    msg["To"] = destino
    msg["Subject"] = ASUNTO
    msg.set_content(texto)
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
            if s.smtp_tls:
                smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
    except Exception as exc:
        raise RuntimeError(f"No se pudo enviar el correo: {exc}") from exc


def enviar_whatsapp(numero: str, texto: str) -> None:
    """Envía por la Cloud API de Meta.

    Ojo: fuera de la ventana de 24 h desde el último mensaje del usuario, Meta
    exige una **plantilla aprobada**; un texto libre se rechaza. Para el resumen
    diario de pagos hay que aprobar una plantilla *utility* y usarla aquí.
    """
    s = get_settings()
    if not (s.whatsapp_token and s.whatsapp_phone_id):
        raise RuntimeError(
            "Falta configurar FINANZAS_WHATSAPP_TOKEN y FINANZAS_WHATSAPP_PHONE_ID "
            "en el servidor"
        )
    url = f"https://graph.facebook.com/{s.whatsapp_api_version}/{s.whatsapp_phone_id}/messages"
    cuerpo = json.dumps(
        {
            "messaging_product": "whatsapp",
            "to": numero,
            "type": "text",
            "text": {"body": texto},
        }
    ).encode("utf-8")
    peticion = urllib.request.Request(  # noqa: S310
        url,
        data=cuerpo,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {s.whatsapp_token}",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=15) as resp:  # noqa: S310
            json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        raise RuntimeError(f"No se pudo hablar con WhatsApp: {exc}") from exc


CANALES = ("telegram", "email", "whatsapp")


def canales_de(config: ConfigNotificaciones) -> list[str]:
    """`ambos` se mantiene como telegram+email (compatibilidad); `todos` = los tres."""
    if config.canal == "todos":
        return list(CANALES)
    if config.canal == "ambos":
        return ["telegram", "email"]
    return [config.canal]


def enviar(config: ConfigNotificaciones, alertas: list[dict]) -> list[str]:
    """Envía por los canales configurados. Devuelve los canales que funcionaron."""
    texto = construir_mensaje(alertas)
    usados: list[str] = []
    errores: list[str] = []

    for canal in canales_de(config):
        try:
            if canal == "telegram":
                if not config.telegram_chat_id:
                    errores.append("telegram: falta el chat ID")
                    continue
                enviar_telegram(config.telegram_chat_id, texto)
            elif canal == "whatsapp":
                if not config.whatsapp_numero:
                    errores.append("whatsapp: falta el número destino")
                    continue
                enviar_whatsapp(config.whatsapp_numero, texto)
            elif canal == "email":
                if not config.email:
                    errores.append("email: falta el correo destino")
                    continue
                enviar_email(config.email, texto)
            else:
                errores.append(f"canal desconocido: {canal}")
                continue
            usados.append(canal)
        except RuntimeError as exc:
            errores.append(str(exc))

    if not usados:
        raise RuntimeError("; ".join(errores) or "No hay canales configurados")
    return usados


def obtener_o_crear(db: Session, usuario) -> ConfigNotificaciones:
    config = db.scalar(
        select(ConfigNotificaciones).where(ConfigNotificaciones.usuario_id == usuario.id)
    )
    if config is None:
        config = ConfigNotificaciones(
            usuario_id=usuario.id,
            canal="telegram",
            email=getattr(usuario, "email", None),
            dias_anticipacion=5,
            activo=False,
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def procesar_notificaciones() -> int:
    """Envía el resumen diario. Idempotente por día (usa `ultima_notificacion`)."""
    engine = make_engine()
    sf = make_session_factory(engine)
    hoy_ = hoy()
    enviadas = 0
    try:
        with sf.begin() as s:
            configs = s.scalars(
                select(ConfigNotificaciones).where(
                    ConfigNotificaciones.activo.is_(True),
                    or_(
                        ConfigNotificaciones.ultima_notificacion.is_(None),
                        ConfigNotificaciones.ultima_notificacion < hoy_,
                    ),
                )
            ).all()
            for config in configs:
                alertas = calcular_alertas(s, config.usuario_id, config.dias_anticipacion)
                if not alertas:
                    continue
                try:
                    enviar(config, alertas)
                except RuntimeError:
                    continue
                config.ultima_notificacion = hoy_
                enviadas += 1
        return enviadas
    finally:
        engine.dispose()
