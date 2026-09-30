"""Configuración central (prefijo FINANZAS_)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="FINANZAS_", extra="ignore")

    database_url: str = "postgresql+psycopg://finanzas:finanzas@localhost:5433/finanzas"

    # Seguridad (JWT)
    secret_key: str = "cambiar-por-un-secreto-largo-y-aleatorio"
    access_token_expire_minutes: int = 1440  # 24 h

    # Zona horaria para calcular "hoy" en los ingresos recurrentes
    timezone: str = "America/Bogota"

    # Tamaño máximo de un archivo que se sube (facturas, extractos). **Tiene que coincidir
    # con `client_max_body_size` de nginx**: si nginx corta antes, el navegador recibe un
    # 413 en HTML y el usuario ve un error que no le dice nada.
    tamano_maximo_archivo_mb: int = 15

    # Scheduler de ingresos recurrentes (deshabilitar en tests)
    scheduler_enabled: bool = True

    # Notificaciones — Telegram (token del bot, global)
    telegram_bot_token: str | None = None

    # Notificaciones — Email (SMTP, global)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_tls: bool = True

    # Notificaciones — WhatsApp (Cloud API de Meta, global)
    # Sin token/phone_id el canal queda deshabilitado y avisa al probarlo.
    whatsapp_token: str | None = None
    whatsapp_phone_id: str | None = None
    whatsapp_api_version: str = "v21.0"

    # OCR de facturas: embeddings opcionales (Ollama) para el tercer nivel del
    # clasificador de artículos. Si `ollama_url` está vacío, el clasificador usa
    # solo historial + diccionario y no sale a la red.
    ollama_url: str | None = None
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_timeout: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
