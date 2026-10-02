"""El «Saldo final» del consolidado tiene que decir lo mismo que el Resumen.

Pasó de verdad: el Resumen (la tabla de cuentas) **sí** restaba el pago de la tarjeta,
pero el «Consolidado mes a mes» lo ignoraba —daba por neutra toda transferencia— y
seguía enseñando millones que ya no estaban en ninguna cuenta. La diferencia era,
al peso, el pago de la tarjeta menos las compras a crédito que el consolidado contaba
como gasto.

La regla: solo es neutra la transferencia **entre cuentas propias** (tiene destino).
Pagar la tarjeta es una transferencia **sin destino**: sale dinero de verdad.
"""

from __future__ import annotations

from test_api import _registrar

from app.recurrencia import hoy


def _cuenta(client, h, nombre: str, saldo: str) -> dict:
    r = client.post(
        "/cuentas",
        headers=h,
        json={"nombre": nombre, "tipo": "ahorro", "saldo_inicial": saldo},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _tarjeta(client, h, nombre: str, tipo: str = "credito") -> dict:
    r = client.post("/tarjetas", headers=h, json={"nombre": nombre, "tipo": tipo})
    assert r.status_code == 201, r.text
    return r.json()


def _movimiento(client, h, **campos) -> dict:
    campos.setdefault("fecha", hoy().isoformat())
    r = client.post("/transacciones", headers=h, json=campos)
    assert r.status_code == 201, r.text
    return r.json()


def _saldo_total(client, h) -> float:
    return float(client.get("/cuentas", headers=h).json()["saldo_total"])


def _ultimo_mes(client, h) -> dict:
    r = client.get("/saldos/consolidado?meses=3", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["meses"][-1]


def _saldo_consolidado(client, h) -> float:
    r = client.get("/saldos/consolidado?meses=3", headers=h)
    assert r.status_code == 200, r.text
    return r.json()["saldo_actual"]


def test_el_pago_de_la_tarjeta_baja_el_saldo_del_consolidado(client):
    """Lo que se paga de la tarjeta sale de la cuenta y el consolidado debe verlo."""
    _, h = _registrar(client)
    cuenta = _cuenta(client, h, "Bancolombia", "5000000")
    tarjeta = _tarjeta(client, h, "AMEX")

    # Lo que dice el extracto y su pago: dinero que sale de la cuenta
    r = client.post(
        f"/tarjetas/{tarjeta['id']}/deudas",
        headers=h,
        json={"moneda": "COP", "monto": "1000000"},
    )
    assert r.status_code == 201, r.text
    r = client.post(
        f"/tarjetas/{tarjeta['id']}/pagos",
        headers=h,
        json={"cuenta_id": cuenta["id"], "monto": "1000000", "moneda": "COP"},
    )
    assert r.status_code == 201, r.text

    assert _saldo_total(client, h) == 4000000.0
    assert _saldo_consolidado(client, h) == 4000000.0, "el consolidado ignoró el pago"

    ultimo = _ultimo_mes(client, h)
    assert ultimo["saldo_final"] == 4000000.0
    # El pago va en «salidas», no en «gastos»: no es consumo
    assert ultimo["transferencias_salientes"] == 1000000.0
    assert ultimo["gastos"] == 0.0


def test_la_compra_con_credito_no_es_gasto_en_el_consolidado(client):
    """La compra con tarjeta de crédito es deuda: no sale de la cuenta todavía."""
    _, h = _registrar(client)
    _cuenta(client, h, "Bancolombia", "5000000")
    credito = _tarjeta(client, h, "AMEX")
    debito = _tarjeta(client, h, "Ahorros", "debito")

    _movimiento(client, h, tipo="gasto", monto="300000", descripcion="Ventilador", tarjeta_id=credito["id"])
    _movimiento(client, h, tipo="gasto", monto="100000", descripcion="Parqueadero", tarjeta_id=debito["id"])

    ultimo = _ultimo_mes(client, h)
    assert ultimo["gastos"] == 100000.0, ultimo
    assert ultimo["saldo_final"] == 4900000.0
    assert _saldo_total(client, h) == 4900000.0
    assert _saldo_consolidado(client, h) == 4900000.0


def test_la_transferencia_entre_cuentas_propias_no_cambia_el_saldo(client):
    """Mover plata de una cuenta tuya a otra no te hace más pobre."""
    _, h = _registrar(client)
    origen = _cuenta(client, h, "Bancolombia", "1000000")
    destino = _cuenta(client, h, "Nequi", "0")

    _movimiento(
        client, h, tipo="transferencia", monto="400000", descripcion="A Nequi",
        cuenta_id=origen["id"], cuenta_destino_id=destino["id"],
    )

    assert _saldo_total(client, h) == 1000000.0
    assert _saldo_consolidado(client, h) == 1000000.0, "una transferencia propia movió el total"
    assert _ultimo_mes(client, h)["transferencias_salientes"] == 0.0
