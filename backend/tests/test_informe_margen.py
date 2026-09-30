"""El informe del mes: coste real, promedios, percentiles y margen por plan.

Es lo que permite decidir precios con datos. Se prueban los números con casos conocidos: si el
cálculo se equivoca, los precios salen mal y el negocio se decide a ciegas.
"""

from __future__ import annotations

from sqlalchemy import text
from test_api import _registrar

from app import informe
from app.config import get_settings


def _admin(client, monkeypatch, email: str = "dueno@example.com"):
    monkeypatch.setattr(get_settings(), "informe_admins", email)
    return _registrar(client, email=email)


def _consumo(engine, email: str, periodo: str, **campos) -> None:
    base = {"lecturas": 0, "consultas": 0, "tokens_entrada": 0, "tokens_salida": 0, "costo_usd": 0, "mb_dia": 0}
    base.update(campos)
    with engine.begin() as conn:
        conn.execute(
            text(
                "insert into consumos_ia (id, usuario_id, periodo, lecturas, consultas, "
                "tokens_entrada, tokens_salida, costo_usd, mb_dia, archivos_dia, dias_medidos) "
                "select gen_random_uuid(), id, :p, :l, :c, :te, :ts, :cu, :mb, 0, 1 "
                "from usuarios where email = :e"
            ),
            {"p": periodo, "l": base["lecturas"], "c": base["consultas"], "te": base["tokens_entrada"],
             "ts": base["tokens_salida"], "cu": base["costo_usd"], "mb": base["mb_dia"], "e": email},
        )


def test_el_informe_calcula_promedios_percentiles_y_margen(client, engine, monkeypatch):
    _, h = _admin(client, monkeypatch)
    # un cliente de cada plan, con consumos conocidos
    _registrar(client, email="u1@example.com")  # basico (por defecto)
    _registrar(client, email="u2@example.com")
    _registrar(client, email="u3@example.com")

    periodo = informe.hoy().strftime("%Y-%m")
    _consumo(engine, "u1@example.com", periodo, lecturas=2, consultas=1, tokens_entrada=2000, costo_usd=0.002, mb_dia=100)
    _consumo(engine, "u2@example.com", periodo, lecturas=4, consultas=3, tokens_entrada=6000, costo_usd=0.006, mb_dia=300)

    # u3 no consumió nada: paga y no gasta (eso también es información)
    datos = client.get("/ia/informe", headers=h).json()
    assert datos["periodo"] == periodo
    assert datos["usuarios"] >= 3

    basico = [p for p in datos["planes"] if p["codigo"] == "basico"][0]
    # tres clientes de verdad: la cuenta del dueño queda fuera (no se paga a sí misma)
    assert basico["usuarios"] == 3
    assert datos["cuentas_del_dueno_excluidas"] == 1
    assert any("cuenta(s) del dueño" in n for n in datos["notas"])
    assert basico["ingreso_cop"] == 18000.0  # 3 × 6.000
    # lecturas: [2, 4] (u3 no tiene fila) → total 6, p50 3, p90 3.8
    assert basico["lecturas"]["total"] == 6
    assert basico["lecturas"]["p50"] == 3
    assert basico["lecturas"]["p90"] == 3.8
    assert basico["lecturas"]["max"] == 4
    # coste real de IA del plan y su margen (con la tasa cargada, si la hay)
    assert basico["costo_ia_usd"] == 0.008
    assert basico["mb_dia"]["total"] == 400
    if datos["cop_por_usd"]:
        assert basico["margen_cop"] is not None
        assert basico["margen_cop"] < basico["ingreso_cop"], "el margen no puede ser mayor que el ingreso"
        assert basico["margen_pct"] > 90, "con estos consumos el margen tiene que ser altísimo"


def test_el_informe_avisa_cuando_falta_el_precio_del_espacio(client, engine, monkeypatch):
    _, h = _admin(client, monkeypatch)
    _registrar(client, email="u1@example.com")
    periodo = informe.hoy().strftime("%Y-%m")
    _consumo(engine, "u1@example.com", periodo, mb_dia=2048)  # 2 GB-mes

    datos = client.get("/ia/informe", headers=h).json()
    assert any("precio por GB-mes" in n for n in datos["notas"])
    basico = [p for p in datos["planes"] if p["codigo"] == "basico"][0]
    assert basico["costo_almacen_usd"] is None, "sin precio no se inventa un coste"
    assert basico["gb_mes"] == 2.0, "pero el volumen sí se informa"


def test_con_precio_del_espacio_el_coste_sale(client, engine, monkeypatch):
    _, h = _admin(client, monkeypatch)
    monkeypatch.setattr(get_settings(), "costo_gb_mes_usd", 0.02)
    _registrar(client, email="u1@example.com")
    periodo = informe.hoy().strftime("%Y-%m")
    _consumo(engine, "u1@example.com", periodo, mb_dia=2048)

    datos = client.get("/ia/informe", headers=h).json()
    basico = [p for p in datos["planes"] if p["codigo"] == "basico"][0]
    assert basico["costo_almacen_usd"] == 0.04, "2 GB-mes a 0,02 USD"


def test_solo_el_dueno_ve_el_informe(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "informe_admins", "dueno@example.com")
    _, h_ajeno = _registrar(client, email="curioso@example.com")
    r = client.get("/ia/informe", headers=h_ajeno)
    assert r.status_code == 403, r.text
    assert "dueño de la app" in r.json()["detail"]

    # y sin configurar a nadie, tampoco
    monkeypatch.setattr(get_settings(), "informe_admins", "")
    _, h_dueno = _registrar(client, email="dueno@example.com")
    assert client.get("/ia/informe", headers=h_dueno).status_code == 403


def test_los_percentiles_con_casos_conocidos(client):
    """p50 y p90 con interpolación: es la diferencia entre decidir con datos y con la media."""
    assert informe._percentil([], 0.5) == 0.0
    assert informe._percentil([5], 0.9) == 5.0
    assert informe._percentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.5) == 5.5
    assert informe._percentil([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.9) == 9.1
    # un cliente pesado mueve el promedio pero casi no el p50
    datos = informe._resumen_de([1, 1, 1, 1, 1, 1, 1, 1, 1, 100])
    assert datos["promedio"] == 10.9
    assert datos["p50"] == 1.0
    assert datos["p90"] == 10.9
    assert datos["max"] == 100.0
