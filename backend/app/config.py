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


@lru_cache
def get_settings() -> Settings:
    return Settings()
