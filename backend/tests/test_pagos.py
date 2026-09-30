"""El cobro: comprar un plan o lecturas, con idempotencia y sin agujeros.

Lo que se protege aquí es dinero y confianza: que el precio lo ponga el catálogo (no el cliente),
que nada se acredite sin pago, y que un aviso repetido de la pasarela no acredite dos veces.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _registrar

from app.config import get_settings


def _orden(client, h, tipo: str, codigo: str) -> dict:
    r = client.post("/pagos/orden", headers=h, json={"tipo": tipo, "codigo": codigo})
    assert r.status_code == 201, r.text
    return r.json()


def _avisar(client, h, referencia: str, estado: str = "pagado", id_externo: str = "ext-1"):
    """Aviso de la pasarela simulada. Exige sesión: sin firma, la firma el usuario."""
    return client.post(
        "/pagos/webhook/simulada",
        headers=h,
        json={"referencia": referencia, "estado": estado, "id_externo": id_externo},
    )


def test_los_paquetes_estan_en_el_catalogo(client):
    _, h = _registrar(client)
    paquetes = client.get("/pagos/paquetes", headers=h).json()
    assert {p["codigo"] for p in paquetes} >= {"lecturas10", "lecturas50"}
    assert all(p["lecturas"] > 0 and Decimal(str(p["precio"])) > 0 for p in paquetes)


def test_el_precio_lo_pone_el_catalogo_no_el_cliente(client):
    _, h = _registrar(client)
    # aunque el cliente mande un precio, se ignora: el cuerpo solo acepta tipo y código
    r = client.post(
        "/pagos/orden", headers=h, json={"tipo": "plan", "codigo": "personal", "monto": "1"}
    )
    assert r.status_code == 201, r.text
    assert Decimal(str(r.json()["monto"])) == Decimal("12000")  # el precio del catálogo


def test_comprar_un_plan_lo_deja_activo_y_con_recibo(client):
    _, h = _registrar(client)
    assert client.get("/ia/cuota", headers=h).json()["plan"] == "basico"

    orden = _orden(client, h, "plan", "pro")
    assert orden["estado"] == "pendiente"
    # sin pagar, el plan no cambia
    assert client.get("/ia/cuota", headers=h).json()["plan"] == "basico"

    assert client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h).status_code == 200
    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["plan"] == "pro"
    assert cuota["lecturas_incluidas"] == 100

    recibos = client.get("/pagos/mios", headers=h).json()
    assert len(recibos) == 1
    assert recibos[0]["estado"] == "pagado"
    assert recibos[0]["referencia"] == orden["referencia"]
    assert recibos[0]["pagado_en"] is not None


def test_un_aviso_repetido_no_acredita_dos_veces(client):
    """Las pasarelas reintentan sus avisos: si cada reintento sumara, el cliente ganaría saldo."""
    _, h = _registrar(client)
    antes = client.get("/ia/cuota", headers=h).json()["lecturas_restantes"]

    orden = _orden(client, h, "paquete", "lecturas10")
    primero = _avisar(client, h, orden["referencia"], id_externo="ext-abc")
    assert primero.status_code == 200 and primero.json()["aplicado_ahora"] is True

    despues = client.get("/ia/cuota", headers=h).json()["lecturas_restantes"]
    assert despues == antes + 10

    # el mismo aviso otra vez (y una tercera)
    for _ in range(2):
        repetido = _avisar(client, h, orden["referencia"], id_externo="ext-abc")
        assert repetido.status_code == 200
        assert repetido.json()["aplicado_ahora"] is False
        assert "ya estaba aplicado" in repetido.json()["mensaje"]

    assert client.get("/ia/cuota", headers=h).json()["lecturas_restantes"] == antes + 10, (
        "el reintento del aviso duplicó las lecturas"
    )
    assert len(client.get("/pagos/mios", headers=h).json()) == 1


def test_un_aviso_de_fallo_no_acredita_nada(client):
    _, h = _registrar(client)
    orden = _orden(client, h, "paquete", "lecturas50")
    r = _avisar(client, h, orden["referencia"], estado="fallido")
    assert r.status_code == 200 and r.json()["estado"] == "fallido"

    assert client.get("/ia/cuota", headers=h).json()["lecturas_restantes"] == 10  # las del plan
    recibos = client.get("/pagos/mios", headers=h).json()
    assert recibos[0]["estado"] == "fallido"


def test_no_se_puede_confirmar_la_orden_de_otro(client):
    _, h_uno = _registrar(client, email="uno@example.com")
    _, h_dos = _registrar(client, email="dos@example.com")
    orden = _orden(client, h_uno, "paquete", "lecturas10")

    r = client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h_dos)
    assert r.status_code == 404, r.text
    assert client.get("/ia/cuota", headers=h_dos).json()["lecturas_restantes"] == 10


def test_cada_orden_lleva_su_referencia(client):
    _, h = _registrar(client)
    una = _orden(client, h, "paquete", "lecturas10")
    otra = _orden(client, h, "paquete", "lecturas10")
    assert una["referencia"] != otra["referencia"]


def test_con_una_pasarela_real_la_confirmacion_simulada_no_existe(client, monkeypatch):
    """Acreditar sin cobrar sería un agujero: con pasarela real, esa puerta se cierra."""
    _, h = _registrar(client)
    monkeypatch.setattr(get_settings(), "pasarela", "wompi")
    r = client.post("/pagos/simular-pago/konta-lo-que-sea", headers=h)
    assert r.status_code in (403, 503), r.text


def test_el_aviso_de_otra_pasarela_no_se_acepta(client):
    _, h = _registrar(client)
    orden = _orden(client, h, "paquete", "lecturas10")
    r = client.post(
        "/pagos/webhook/mercadopago",
        headers=h,
        json={"referencia": orden["referencia"], "estado": "pagado"},
    )
    assert r.status_code == 404, r.text
    assert client.get("/ia/cuota", headers=h).json()["lecturas_restantes"] == 10


def test_un_aviso_de_una_orden_que_no_existe_no_revienta(client):
    _, h = _registrar(client)
    r = _avisar(client, h, "konta-inventada")
    assert r.status_code == 404
    assert "No hay ninguna orden" in r.json()["detail"]


def test_el_aviso_simulado_sin_sesion_no_acredita(client):
    """Sin firma de pasarela y sin sesión no se acredita nada: sería un agujero."""
    _, h = _registrar(client)
    orden = _orden(client, h, "paquete", "lecturas10")
    sin_sesion = client.post(
        "/pagos/webhook/simulada",
        json={"referencia": orden["referencia"], "estado": "pagado"},
    )
    assert sin_sesion.status_code == 401, sin_sesion.text
    assert client.get("/ia/cuota", headers=h).json()["lecturas_restantes"] == 10


def test_un_pago_de_plan_da_un_mes_y_no_para_siempre(client):
    """Sin vencimiento, una sola compra dejaría el plan para siempre (y el coste seguiría corriendo)."""
    _, h = _registrar(client)
    orden = _orden(client, h, "plan", "pro")
    assert client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h).status_code == 200

    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["plan"] == "pro"
    assert cuota["plan_hasta"] is not None, "el plan tiene que tener fecha de vencimiento"
    assert cuota["dias_de_plan"] == 30
    assert cuota["plan_por_vencer"] is False


def test_renovar_antes_de_vencer_extiende_desde_donde_estaba(client, engine):
    """Quien renueva el día 20 no pierde los 10 días que le quedaban."""
    from sqlalchemy import text as sql_text

    from app.recurrencia import hoy

    _, h = _registrar(client)
    for _ in range(2):
        orden = _orden(client, h, "plan", "personal")
        assert client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h).status_code == 200

    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["dias_de_plan"] == 60, f"dos pagos seguidos son dos meses: {cuota['dias_de_plan']}"

    # y si estaba a punto de vencer, se extiende desde ahí
    with engine.begin() as conn:
        conn.execute(
            sql_text("update usuarios set plan_hasta = :hasta where plan_hasta is not null"),
            {"hasta": hoy()},
        )
    orden = _orden(client, h, "plan", "personal")
    client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h)
    assert client.get("/ia/cuota", headers=h).json()["dias_de_plan"] == 30


def test_al_vencer_el_plan_se_vuelve_al_base_y_las_lecturas_compradas_se_respetan(client, engine):
    from sqlalchemy import text as sql_text

    from app.pagos import vencer_planes
    from app.recurrencia import hoy

    _, h = _registrar(client)
    # compra un plan y un paquete de lecturas
    orden = _orden(client, h, "plan", "pro")
    client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h)
    paquete = _orden(client, h, "paquete", "lecturas10")
    client.post(f"/pagos/simular-pago/{paquete['referencia']}", headers=h)
    assert client.get("/ia/cuota", headers=h).json()["lecturas_restantes"] == 110  # 100 + 10

    # pasa el tiempo
    with engine.begin() as conn:
        conn.execute(
            sql_text("update usuarios set plan_hasta = :ayer where plan_hasta is not null"),
            {"ayer": hoy() - __import__("datetime").timedelta(days=1)},
        )

    from sqlalchemy.orm import sessionmaker

    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        vencidos = vencer_planes(s)
    assert len(vencidos) == 1

    cuota = client.get("/ia/cuota", headers=h).json()
    assert cuota["plan"] == "basico", "vuelve al plan base"
    assert cuota["plan_hasta"] is None, "y sin fecha: no hay nada más que vencer"
    assert cuota["lecturas_restantes"] == 20, "las 10 compradas se quedan (se pagaron) + 10 del base"

    # idempotente: correrlo otra vez no cambia nada
    with sf.begin() as s:
        assert vencer_planes(s) == []


def test_avisa_antes_de_que_venza_el_plan(client, engine):
    """Que el cliente se entere antes, no cuando ya perdió el plan."""
    from datetime import timedelta

    from sqlalchemy import text as sql_text

    from app.alertas import calcular_alertas
    from app.recurrencia import hoy

    _, h = _registrar(client)
    orden = _orden(client, h, "plan", "personal")
    client.post(f"/pagos/simular-pago/{orden['referencia']}", headers=h)

    with engine.begin() as conn:
        usuario_id = conn.execute(
            sql_text("select id from usuarios order by creado_en desc limit 1")
        ).scalar()
        conn.execute(
            sql_text("update usuarios set plan_hasta = :hasta where id = :id"),
            {"hasta": hoy() + timedelta(days=3), "id": usuario_id},
        )
    from sqlalchemy.orm import sessionmaker

    with sessionmaker(bind=engine).begin() as s:
        alertas = calcular_alertas(s, usuario_id)
    planes = [a for a in alertas if a["tipo"] == "plan_por_vencer"]
    assert planes, [a["tipo"] for a in alertas]
    assert "vence" in planes[0]["titulo"]
    assert planes[0]["dias_restantes"] == 3
