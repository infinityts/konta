"""Un saldo «actual» no cuenta el futuro.

Pasó de verdad: un sueldo recurrente quedó fechado **un mes por delante** (30/10) y el saldo
de la cuenta lo sumaba como si ya estuviera cobrado, así que se veía el doble del saldo real.
"""

from __future__ import annotations

from datetime import date, timedelta

from test_api import _registrar


def _cuenta(client, h, saldo_inicial: str) -> dict:
    r = client.post(
        "/cuentas",
        headers=h,
        json={"nombre": "Bancolombia", "tipo": "ahorro", "saldo_inicial": saldo_inicial},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _movimiento(client, h, **campos) -> dict:
    r = client.post("/transacciones", headers=h, json=campos)
    assert r.status_code == 201, r.text
    return r.json()


def test_el_saldo_no_cuenta_los_movimientos_futuros(client):
    _, h = _registrar(client)
    cuenta = _cuenta(client, h, "11837735")
    hoy = date.today()
    proximo_mes = hoy + timedelta(days=30)

    _movimiento(
        client, h, tipo="ingreso", monto="11783952", fecha=proximo_mes.isoformat(),
        descripcion="Ingreso Intraway", cuenta_id=cuenta["id"],
    )
    saldos = client.get("/cuentas", headers=h).json()
    assert float(saldos["cuentas"][0]["saldo_actual"]) == 11837735.0, "contó un ingreso futuro"
    assert float(saldos["saldo_total"]) == 11837735.0

    # y el de hoy sí cuenta
    _movimiento(
        client, h, tipo="gasto", monto="100000", fecha=hoy.isoformat(),
        descripcion="Compra de hoy", cuenta_id=cuenta["id"],
    )
    saldos = client.get("/cuentas", headers=h).json()
    assert float(saldos["cuentas"][0]["saldo_actual"]) == 11737735.0, "no contó el de hoy"


def test_los_gastos_futuros_tampoco_cuentan(client):
    _, h = _registrar(client)
    cuenta = _cuenta(client, h, "1000000")
    _movimiento(
        client, h, tipo="gasto", monto="500000", fecha=(date.today() + timedelta(days=10)).isoformat(),
        descripcion="Pago programado", cuenta_id=cuenta["id"],
    )
    saldos = client.get("/cuentas", headers=h).json()
    assert float(saldos["cuentas"][0]["saldo_actual"]) == 1000000.0
