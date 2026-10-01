"""Fixtures de pytest para el backend de Finly.

Usa FINANZAS_TEST_DATABASE_URL (o FINANZAS_DATABASE_URL). Si no está definida,
los tests se omiten. Antes de cada test se migra (si hace falta) y se truncan
las tablas para aislamiento.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

TEST_URL = os.environ.get("FINANZAS_TEST_DATABASE_URL") or os.environ.get(
    "FINANZAS_DATABASE_URL"
)

if TEST_URL:
    os.environ["FINANZAS_DATABASE_URL"] = TEST_URL
    # Deshabilitar el scheduler en tests
    os.environ["FINANZAS_SCHEDULER_ENABLED"] = "false"


@pytest.fixture(scope="session")
def engine():
    if not TEST_URL:
        pytest.skip("FINANZAS_TEST_DATABASE_URL no definida")
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    command.upgrade(cfg, "head")

    from app.db import make_engine

    eng = make_engine(TEST_URL)
    yield eng
    eng.dispose()


@pytest.fixture()
def client(engine):
    from fastapi.testclient import TestClient

    # Aislamiento: truncar todo antes de cada test
    with engine.begin() as conn:
        conn.execute(
            text(
                # `intentos_login` no cuelga de `usuarios` (se indexa por texto), así que el
                # CASCADE no la limpia: sin nombrarla, los contadores de fallos se acumularían
                # entre tests y unos harían fallar a otros.
                "TRUNCATE transacciones, suscripciones, tarjetas, "
                "categorias, usuarios, tasas_cambio, intentos_login CASCADE"
            )
        )

    from app.main import app

    with TestClient(app) as c:
        yield c
