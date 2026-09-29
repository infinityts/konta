"""El previo de importación con un extracto de **cuenta** (no solo tarjetas)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import sessionmaker
from test_api import _registrar

from app.models import Extracto


def test_el_previo_admite_lineas_sin_movimiento(client, engine):
    """Los intereses y comisiones que **declara el corte** no son movimientos.

    Se sintetizan como líneas a importar con `movimiento_id` nulo. Con el esquema exigiendo
    un UUID, `GET /extractos/{id}/importar` devolvía **500** en un extracto de cuenta
    (con uno de tarjeta no se notaba porque no declara intereses).
    """
    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]

    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        extracto = Extracto(
            usuario_id=usuario_id,
            tipo="cuenta",
            formato="pdf",
            nombre_archivo="cuenta.pdf",
            moneda="COP",
            banco="Banco",
            intereses=Decimal("97624.49"),
            otros_cargos=Decimal("12000.00"),
            fecha_corte=date(2026, 8, 28),
        )
        s.add(extracto)
        s.flush()
        eid = str(extracto.id)

    r = client.get(f"/extractos/{eid}/importar?incluir_cuotas_anteriores=false", headers=h)
    assert r.status_code == 200, r.text
    lineas = r.json()["lineas"]
    assert any(li["movimiento_id"] is None for li in lineas), "intereses y comisiones van sin movimiento"
