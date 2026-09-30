"""Una compra con tarjeta de **crédito** no es «sin cuenta».

Es deuda de la tarjeta: ese dinero no sale de ninguna cuenta hasta que pagas la tarjeta. Al
contarla como «sin cuenta», el Resumen la restaba dos veces (al comprar y al pagar) y pedía
asignarle una cuenta, que no es lo que corresponde.
"""

from __future__ import annotations

from test_api import _registrar


def _cuenta(client, h, nombre: str, saldo: str) -> dict:
    r = client.post(
        "/cuentas", headers=h, json={"nombre": nombre, "tipo": "ahorro", "saldo_inicial": saldo}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _tarjeta(client, h, nombre: str, tipo: str) -> dict:
    r = client.post("/tarjetas", headers=h, json={"nombre": nombre, "tipo": tipo})
    assert r.status_code == 201, r.text
    return r.json()


def _gasto(client, h, monto: str, descripcion: str, **extra) -> dict:
    r = client.post(
        "/transacciones",
        headers=h,
        json={"tipo": "gasto", "monto": monto, "fecha": "2026-09-29", "descripcion": descripcion, **extra},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_la_compra_con_credito_no_entra_en_sin_cuenta(client):
    _, h = _registrar(client)
    _cuenta(client, h, "Bancolombia", "1000000")
    credito = _tarjeta(client, h, "AMEX", "credito")
    debito = _tarjeta(client, h, "Ahorros", "debito")

    _gasto(client, h, "200000", "Ventilador", tarjeta_id=credito["id"])   # deuda de la tarjeta
    _gasto(client, h, "50000", "Parqueadero", tarjeta_id=debito["id"])    # sale de la cuenta
    _gasto(client, h, "30000", "Efectivo")                                # efectivo, sin medio

    saldos = client.get("/cuentas", headers=h).json()
    # solo el débito y el efectivo: la de crédito es deuda de la tarjeta
    assert float(saldos["sin_cuenta"]) == -80000.0, saldos["sin_cuenta"]
    assert saldos["sin_cuenta_movimientos"] == 2, saldos["sin_cuenta_movimientos"]
    assert float(saldos["saldo_total"]) == 920000.0, saldos["saldo_total"]

    # y la cuenta, intacta por la compra de crédito
    assert float(saldos["cuentas"][0]["saldo_actual"]) == 1000000.0
