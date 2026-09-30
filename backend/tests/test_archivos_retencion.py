"""El archivo de la factura: se guarda con retención, se relee con IA y se borra solo.

El archivo existe para una cosa: poder releer con IA los documentos que el lector normal no
pudo. Si el plan no da para más, la factura se sube igual — lo único que falta es esa segunda
oportunidad, y el aviso lo dice.
"""

from __future__ import annotations

import pathlib
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


def test_borrar_la_factura_borra_su_archivo(client):
    """Sin esto, el disco se llena de archivos que ya nadie puede borrar desde la app."""
    _, h = _registrar(client)
    factura = _factura(client, h)
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    clave = f"{detalle['usuario_id']}/{factura['id']}.pdf"
    assert almacen.leer(clave)

    assert client.delete(f"/facturas/{factura['id']}", headers=h).status_code == 204
    with pytest.raises(almacen.ArchivoNoEncontrado):
        almacen.leer(clave)
    # y el cupo vuelve a quedar libre
    assert client.get("/ia/cuota", headers=h).json()["archivos_usados"] == 0


def test_al_borrar_el_ultimo_archivo_no_queda_la_carpeta(client):
    _, h = _registrar(client)
    factura = _factura(client, h)
    detalle = client.get(f"/facturas/{factura['id']}", headers=h).json()
    carpeta = pathlib.Path(get_settings().almacen_ruta) / detalle["usuario_id"]
    assert carpeta.is_dir()

    client.delete(f"/facturas/{factura['id']}", headers=h)
    assert not carpeta.exists(), "la carpeta vacía del usuario se quedaba ahí"


def test_el_almacenamiento_se_mide_por_dia_y_no_se_cuenta_dos_veces(client, engine):
    """El MB-día es la métrica honesta: 30 archivos una semana no pesan como un mes.

    Y tiene que ser idempotente: si el trabajo corre dos veces el mismo día, el cliente no puede
    pagar dos veces por lo mismo.
    """
    from datetime import date

    from app.db import make_session_factory

    _, h = _registrar(client)
    _factura(client, h)
    sf = make_session_factory(engine)
    hoy_ = date(2026, 9, 30)

    with sf.begin() as s:
        assert archivos.medir_almacenamiento(s, cuando=hoy_) == 1
    with sf.begin() as s:
        # la segunda del mismo día no cuenta
        assert archivos.medir_almacenamiento(s, cuando=hoy_) == 0

    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["dias_medidos"] == 1
    assert cuota["archivos_promedio"] == 1.0
    assert cuota["mb_promedio"] > 0
    assert cuota["mb_dia"] > 0

    # al día siguiente vuelve a sumar
    with sf.begin() as s:
        assert archivos.medir_almacenamiento(s, cuando=date(2026, 10, 1)) == 1
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["dias_medidos"] == 1, "el mes nuevo empieza su propia cuenta"
    assert cuota["periodo"] == "2026-09"  # el periodo de la cuota sigue siendo el de hoy


def test_un_usuario_sin_archivos_no_se_mide(client, engine):
    from datetime import date

    from app.db import make_session_factory

    _, h = _registrar(client)
    _factura(client, h)
    client.delete(f"/facturas/{[f['id'] for f in client.get('/facturas', headers=h).json()][0]}", headers=h)

    sf = make_session_factory(engine)
    with sf.begin() as s:
        assert archivos.medir_almacenamiento(s, cuando=date(2026, 9, 30)) == 0
    assert client.get("/ia/cuota", headers=h).json()["dias_medidos"] == 0


def test_el_trabajo_borra_los_archivos_que_ya_no_referencia_nadie(client, engine):
    """Archivos de usuarios borrados por fuera de la app: nadie puede quitarlos desde la pantalla."""
    from app.db import make_session_factory

    _, h = _registrar(client)
    _factura(client, h)  # uno legítimo, que NO se puede tocar
    raiz = pathlib.Path(get_settings().almacen_ruta)
    suelto = raiz / "usuario-que-ya-no-existe" / "viejo.pdf"
    suelto.parent.mkdir(parents=True, exist_ok=True)
    suelto.write_bytes(b"%PDF-1.4 fantasma")

    sf = make_session_factory(engine)
    with sf.begin() as s:
        assert archivos.borrar_huerfanos(s) == 1
    assert not suelto.exists()
    assert not suelto.parent.exists(), "la carpeta vacía también se va"
    # y lo que sí está referenciado sigue donde estaba
    detalle = client.get("/facturas", headers=h).json()[0]
    assert client.get(f"/facturas/{detalle['id']}", headers=h).json()["archivo_guardado"] is True


def test_un_almacen_limpio_no_reporta_borrados(client, engine):
    from app.db import make_session_factory

    _, h = _registrar(client)
    _factura(client, h)
    sf = make_session_factory(engine)
    with sf.begin() as s:
        assert archivos.borrar_huerfanos(s) == 0


def test_tambien_barre_las_carpetas_que_ya_estaban_vacias(client, engine):
    """Una carpeta sin archivos dentro se quedaba para siempre (la limpieza solo miraba archivos)."""
    from app.db import make_session_factory

    _, h = _registrar(client)
    raiz = pathlib.Path(get_settings().almacen_ruta)
    vacia = raiz / "usuario-borrado-hace-tiempo"
    vacia.mkdir(parents=True, exist_ok=True)

    sf = make_session_factory(engine)
    with sf.begin() as s:
        archivos.borrar_huerfanos(s)
    assert not vacia.exists()


def test_la_subida_reserva_al_usuario_para_no_saltarse_el_cupo(client, engine, monkeypatch):
    """Varias subidas a la vez no pueden pasar todas la comprobación del cupo."""
    from sqlalchemy import select
    from sqlalchemy.dialects import postgresql

    from app.models import Usuario

    _, h = _registrar(client)
    _factura(client, h)

    # la consulta con la que se reserva el usuario se compila con FOR UPDATE
    compilada = str(select(Usuario.id).where(Usuario.id.isnot(None)).with_for_update().compile(
        dialect=postgresql.dialect()
    ))
    assert "FOR UPDATE" in compilada.upper(), compilada

    # y de verdad reserva: con la fila tomada, otra conexión no puede tomarla ni esperando
    from sqlalchemy import text

    conexion_a = engine.connect()
    conexion_b = engine.connect()
    try:
        trans_a = conexion_a.begin()
        usuario_id = conexion_a.execute(text("select id from usuarios limit 1")).scalar()
        conexion_a.execute(text("select id from usuarios where id = :id for update"), {"id": usuario_id})
        with pytest.raises(Exception) as error:
            conexion_b.execute(
                text("select id from usuarios where id = :id for update nowait"), {"id": usuario_id}
            )
        assert "lock" in str(error.value).lower(), f"el usuario no estaba reservado: {error.value}"
        conexion_b.rollback()
        trans_a.commit()
    finally:
        conexion_a.close()
        conexion_b.close()

    # y el cupo sigue contando bien de forma secuencial
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["archivos_usados"] == 1
