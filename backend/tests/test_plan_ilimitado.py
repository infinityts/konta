"""El plan de PDFs ilimitados: sin tope de cantidad, con tope de peso.

Lo que cuesta de verdad es el espacio, no el número de archivos. Este plan lo refleja: se pueden
guardar todos los documentos que se quieran (mientras quepan en el peso del plan) y cuando no
caben, el aviso habla de peso y de días, no de «tu plan guarda 30 archivos».
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text
from test_api import _pdf_minimo, _registrar

from app import archivos
from app.config import get_settings


@pytest.fixture(autouse=True)
def almacen_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "almacen_ruta", str(tmp_path / "archivos"))
    yield


def _subir(client, h, nombre: str):
    return client.post(
        "/facturas",
        headers=h,
        files={"archivo": (nombre, _pdf_minimo(f"Monto: $10.000\nDoc {nombre}\n"), "application/pdf")},
    )


def _plan(client, h, codigo: str) -> None:
    """Cambia de plan (el cobro ya está probado aparte)."""
    r = client.post("/pagos/orden", headers=h, json={"tipo": "plan", "codigo": codigo})
    assert r.status_code == 201, r.text
    referencia = r.json()["referencia"]
    assert client.post(f"/pagos/simular-pago/{referencia}", headers=h).status_code == 200


def test_el_catalogo_lo_ofrece_como_ilimitado(client):
    _, h = _registrar(client)
    planes = {p["codigo"]: p for p in client.get("/ia/planes", headers=h).json()}
    assert "ilimitado" in planes, "el plan tiene que estar en el catálogo"
    ilimitado = planes["ilimitado"]
    assert ilimitado["archivos_incluidos"] is None, "sin tope de cantidad"
    assert ilimitado["almacenamiento_mb"] == 1024, "con tope de peso"
    assert ilimitado["retencion_dias"] == 15
    # y el Básico sigue con su tope de cantidad
    assert planes["basico"]["archivos_incluidos"] == 30


def test_guarda_mas_archivos_que_el_tope_del_basico(client):
    """Lo que el plan promete: pasar de 30 documentos sin que la app se pare."""
    _, h = _registrar(client)
    _plan(client, h, "ilimitado")

    for i in range(33):  # el Básico se queda en 30
        r = _subir(client, h, f"doc{i}.pdf")
        assert r.status_code == 201, r.text
        assert r.json()["archivo_guardado"] is True, f"el archivo {i} no se guardó"

    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["archivos_usados"] == 33
    assert cuota["archivos_incluidos"] is None
    assert cuota["retencion_dias"] == 15


def test_el_tope_de_peso_si_manda_y_lo_explica_en_peso(client, monkeypatch):
    """Sin tope de cantidad, el que manda es el peso — y el aviso tiene que hablar de peso."""
    _, h = _registrar(client)
    _plan(client, h, "ilimitado")
    # un plan diminuto en peso (no se sube 1 GB en un test) y ya casi lleno
    monkeypatch.setattr(archivos, "limites", lambda db, u: (None, 15, 1))  # 1 MB
    # a 100 bytes del tope: cualquier PDF de verdad (más de 500 bytes) no cabe
    monkeypatch.setattr(archivos, "uso", lambda db, u: (50, 1024 * 1024 - 100))

    r = _subir(client, h, "no-cabe.pdf")
    assert r.status_code == 201, "la factura se sube igual: lo que falta es el archivo guardado"
    assert r.json()["archivo_guardado"] is False
    aviso = r.json()["archivo_aviso"] or ""
    assert "MB" in aviso, f"el aviso tiene que hablar de peso: {aviso}"
    assert "15 días" in aviso, f"y decir cuándo se liberan solos: {aviso}"
    assert "archivos a la vez" not in aviso, "aquí la cantidad no es el problema"


def test_al_plan_ilimitado_no_se_le_habla_de_cantidad_de_archivos(client, monkeypatch):
    """El mensaje del límite tiene que ser el del problema real."""
    from sqlalchemy.orm import sessionmaker

    from app.db import make_engine
    from app.models import Usuario

    _, h = _registrar(client)
    _plan(client, h, "ilimitado")
    monkeypatch.setattr(archivos, "limites", lambda db, u: (None, 15, 1))  # 1 MB
    monkeypatch.setattr(archivos, "uso", lambda db, u: (500, 2 * 1024 * 1024))  # 2 MB usados

    sf = sessionmaker(bind=make_engine())
    with sf.begin() as s:
        usuario = s.query(Usuario).filter(Usuario.email == "dueno-duplicado@example.com").first() or (
            s.query(Usuario).order_by(Usuario.creado_en.desc()).first()
        )
        cabe, motivo = archivos.hay_sitio(s, usuario, 1024)
    assert cabe is False
    assert "2,0 MB" in motivo, motivo
    assert "1,0 MB" in motivo, motivo
    assert "15 días" in motivo
    assert "archivos a la vez" not in motivo


def test_el_informe_da_el_tamano_medio_para_elegir_el_tope(client, engine, monkeypatch):
    """El tope se elige con datos: el informe dice cuánto pesa un archivo y cuántos se guardan."""

    from app import informe

    monkeypatch.setattr(get_settings(), "informe_admins", "dueno@example.com")
    _, h = _registrar(client, email="dueno@example.com")
    _registrar(client, email="cliente@example.com")
    periodo = informe.hoy().strftime("%Y-%m")
    with engine.begin() as conn:
        conn.execute(
            text(
                "insert into consumos_ia (id, usuario_id, periodo, mb_dia, archivos_dia, dias_medidos) "
                "select gen_random_uuid(), id, :p, 300, 30, 10 from usuarios where email = :e"
            ),
            {"p": periodo, "e": "cliente@example.com"},
        )

    datos = client.get("/ia/informe", headers=h).json()
    basico = [p for p in datos["planes"] if p["codigo"] == "basico"][0]
    assert basico["archivos_promedio"] == 3.0, "30 archivos-día en 10 días medidos"
    assert basico["tamano_medio_archivo_mb"] == 10.0, "300 MB-día entre 30 archivos-día"
    assert Decimal(str(basico["mb_dia"]["total"])) == Decimal("300")
