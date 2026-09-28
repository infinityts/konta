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


@lru_cache
def get_settings() -> Settings:
    return Settings()
