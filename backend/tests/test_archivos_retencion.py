"""El archivo de la factura: se guarda con retención, se relee con IA y se borra solo.

El archivo existe para una cosa: poder releer con IA los documentos que el lector normal no
pudo. Si el plan no da para más, la factura se sube igual — lo único que falta es esa segunda
oportunidad, y el aviso lo dice.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import text
from test_api import _pdf_minimo, _registrar

from app import almacen, archivos, ia
from app.config import get_settings
from app.db import make_session_factory
from app.ia import LecturaIa


@pytest.fixture(autouse=True)
def almacen_temporal(tmp_path, monkeypatch):
    """Cada test guarda en su propia carpeta, no en el disco de verdad."""
    monkeypatch.setattr(get_settings(), "almacen_ruta", str(tmp_path / "archivos"))
    yield


def _factura(client, h, texto: str = "Monto: $46.477\nFecha: 30/09/2026\n", nombre="f.pdf") -> dict:
    r = client.post(
        "/facturas",
        headers=h,
        files={"archivo": (nombre, _pdf_minimo(texto), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _stub(monkeypatch, monto="99999", lineas=None):
    def falso(contenido, nombre, tipo, contrasena=None):
        return LecturaIa(
            texto="EMPRESA X\nMonto: $99.999\n",
            campos={
                "monto": Decimal(monto),
                "fecha": "2026-10-01",
                "emisor": "EMPRESA X",
                "lineas": lineas or [],
            },
            tokens_entrada=1200,
            tokens_salida=300,
            costo_usd=Decimal("0.0008"),
        )

    monkeypatch.setattr(ia, "leer_documento", falso)


def test_al_subir_se_guarda_el_archivo_con_su_fecha_de_borrado(client):
    _, h = _registrar(client)
    factura = _factura(client, h)
    assert factura["archivo_guardado"] is True
    assert factura["archivo_expira_en"] is not None
    assert factura["archivo_aviso"] is None

    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert detalle["archivo_guardado"] is True
    # y el archivo está de verdad en el almacén
    clave = f"{detalle['usuario_id']}/{factura['id']}.pdf"
    assert almacen.leer(clave).startswith(b"%PDF")


def test_sin_plan_no_se_guarda_mas_de_lo_permitido_y_se_explica(client, monkeypatch):
    _, h = _registrar(client)
    # un plan de 1 archivo: el segundo ya no cabe, pero la factura se sube igual
    monkeypatch.setattr(archivos, "limites", lambda db, u: (1, 7, 60))
    primera = _factura(client, h, nombre="uno.pdf")
    assert primera["archivo_guardado"] is True

    segunda = _factura(client, h, nombre="dos.pdf")
    assert segunda["archivo_guardado"] is False
    assert "Tu plan guarda 1 archivos" in (segunda["archivo_aviso"] or "")
    # y la factura quedó igual de útil: tiene su monto leído
    assert Decimal(str(segunda["monto_detectado"])) == Decimal("46477")


def test_releer_con_ia_reemplaza_la_lectura_de_la_misma_factura(client, monkeypatch):
    _, h = _registrar(client)
    factura = _factura(client, h)
    assert Decimal(str(factura["monto_detectado"])) == Decimal("46477")

    _stub(monkeypatch)
    r = client.post(f"/facturas/{factura['id']}/leer-con-ia", headers=h)
    assert r.status_code == 200, r.text
    detalle = r.json()
    # la misma factura, con la lectura nueva
    assert detalle["id"] == factura["id"]
    assert Decimal(str(detalle["monto_detectado"])) == Decimal("99999")
    assert detalle["fecha_detectada"] == "2026-10-01"
    assert detalle["leida_con_ia"] is True
    assert detalle["emisor_nombre"] == "EMPRESA X"
    # no se creó otra factura
    assert len(client.get("/facturas", headers=h).json()) == 1
    # y se cobró una lectura del plan
    assert client.get("/ia/cuota", headers=h).json()["lecturas_usadas"] == 1


def test_releer_con_ia_no_toca_lo_que_ya_estaba_registrado(client, monkeypatch):
    _, h = _registrar(client)
    factura = _factura(client, h, "PILAS AA 7.300\nLECHE 4.500\nTOTAL 11.800\n")
    detalle = client.post(
        f"/facturas/{factura['id']}/lineas",
        headers=h,
        json={"texto": "PILAS AA 7.300\nLECHE 4.500\n"},
    ).json()
    assert detalle["lineas"], "el test necesita líneas leídas"
    # una línea se registra (genera movimiento) y otra se añade a mano
    client.post(f"/facturas/{factura['id']}/confirmar", headers=h, json={})
    client.post(
        f"/facturas/{factura['id']}/lineas/agregar",
        headers=h,
        json={"descripcion": "AÑADIDA A MANO", "valor_total": "1000"},
    )
    antes = client.get(f"/facturas/{factura['id']}", headers=h).json()
    registradas = [li for li in antes["lineas"] if li["transaccion_id"] is not None]
    manuales = [li for li in antes["lineas"] if li["origen"] == "agregada"]
    assert registradas, "el test necesita al menos una línea registrada"
    assert manuales

    _stub(monkeypatch, monto="11800", lineas=[{"descripcion": "PILAS AA", "valor": Decimal("7300")}])
    despues = client.post(f"/facturas/{factura['id']}/leer-con-ia", headers=h).json()
    assert any(li["id"] in [x["id"] for x in registradas] for li in despues["lineas"])
    assert any(li["id"] in [x["id"] for x in manuales] for li in despues["lineas"])
    assert any(li["origen"] == "ia" for li in despues["lineas"])


def test_si_no_hay_archivo_guardado_se_explica(client, monkeypatch):
    _, h = _registrar(client)
    factura = _factura(client, h)
    # el usuario borra el archivo a propósito
    assert client.delete(f"/facturas/{factura['id']}/archivo", headers=h).status_code == 204
    assert client.get(f"/facturas/{factura['id']}", headers=h).json()["archivo_guardado"] is False

    _stub(monkeypatch)
    r = client.post(f"/facturas/{factura['id']}/leer-con-ia", headers=h)
    assert r.status_code == 409, r.text
    assert "Vuelve a subir el documento" in r.json()["detail"]
    # y no se cobró nada
    assert client.get("/ia/cuota", headers=h).json()["lecturas_usadas"] == 0


def test_la_retencion_borra_el_archivo_y_deja_la_factura(client, engine, monkeypatch):
    _, h = _registrar(client)
    factura = _factura(client, h)
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    clave = f"{detalle['usuario_id']}/{factura['id']}.pdf"
    assert almacen.leer(clave)

    # se adelanta el reloj de la retención
    with engine.begin() as conn:
        conn.execute(
            text("update facturas set archivo_expira_en = :cuando where id = :id"),
            {"cuando": datetime.now(UTC) - timedelta(days=1), "id": factura["id"]},
        )

    sf = make_session_factory(engine)
    with sf.begin() as s:
        borrados = archivos.borrar_archivos_vencidos(s)
    assert borrados == 1

    # la factura sigue, sin archivo
    despues = client.get(f"/facturas/{factura['id']}", headers=h).json()
    assert despues["archivo_guardado"] is False
    assert Decimal(str(despues["monto_detectado"])) == Decimal("46477")


def test_la_cuota_ensena_el_almacenamiento(client):
    _, h = _registrar(client)
    _factura(client, h)
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["archivos_usados"] == 1
    assert cuota["archivos_incluidos"] == 30
    assert cuota["mb_usados"] > 0
    assert cuota["retencion_dias"] == 7


def test_el_mismo_archivo_no_se_duplica_en_el_almacen(client):
    """La clave lleva el id de la factura: dos facturas no se pisan el archivo."""
    _, h = _registrar(client)
    una = _factura(client, h, nombre="a.pdf")
    otra = _factura(client, h, nombre="b.pdf")
    d1 = client.get(f"/facturas/{una['id']}", headers=h).json()
    d2 = client.get(f"/facturas/{otra['id']}", headers=h).json()
    assert almacen.leer(f"{d1['usuario_id']}/{una['id']}.pdf")
    assert almacen.leer(f"{d2['usuario_id']}/{otra['id']}.pdf")
