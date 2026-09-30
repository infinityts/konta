"""Comprobar que una copia de la base tiene los mismos números (lo que decide una migración)."""

from __future__ import annotations

from sqlalchemy.orm import sessionmaker
from test_api import _registrar

from app import verificacion


def _con_datos(client, email: str = "u@example.com"):
    _, h = _registrar(client, email=email)
    cuenta = client.post(
        "/cuentas", headers=h,
        json={"nombre": "Bancolombia", "tipo": "ahorro", "saldo_inicial": "2000000"},
    ).json()
    client.post("/transacciones", headers=h, json={
        "tipo": "ingreso", "monto": "3000000", "fecha": "2026-09-01", "descripcion": "Salario",
        "cuenta_id": cuenta["id"],
    })
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "450000", "fecha": "2026-09-10", "descripcion": "Mercado",
        "cuenta_id": cuenta["id"],
    })
    return h


def test_una_copia_identica_no_tiene_problemas(client, engine):
    _con_datos(client)
    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        resumen = verificacion.resumen_de(s)
    assert resumen["tablas"]["usuarios"] >= 1
    assert resumen["tablas"]["transacciones"] == 2
    assert resumen["dinero"]["total_ingresos"] == 3000000.0
    assert resumen["dinero"]["total_gastos"] == 450000.0
    # el saldo: 2.000.000 + 3.000.000 − 450.000
    assert list(resumen["saldos"].values()) == [4550000.0]
    assert verificacion.comparar(resumen, resumen) == []


def test_detecta_una_fila_que_falta(client, engine):
    _con_datos(client)
    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        original = verificacion.resumen_de(s)

    # la «copia» perdió una transacción
    copia = {**original, "tablas": {**original["tablas"], "transacciones": 1}}
    problemas = verificacion.comparar(original, copia)
    assert any("transacciones: 2 filas en el original, 1 en la copia" in p for p in problemas)


def test_detecta_un_monto_cambiado_aunque_el_numero_de_filas_coincida(client, engine):
    """El caso traicionero: mismas filas, un monto distinto. La huella lo delata."""
    _con_datos(client)
    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        original = verificacion.resumen_de(s)

    with engine.begin() as conn:
        from sqlalchemy import text as sql_text

        conn.execute(sql_text("update transacciones set monto = 999999 where tipo = 'gasto'"))
    with sf.begin() as s:
        copia = verificacion.resumen_de(s)

    assert copia["tablas"]["transacciones"] == original["tablas"]["transacciones"], "mismas filas"
    problemas = verificacion.comparar(original, copia)
    assert any("huella distinta" in p for p in problemas), problemas
    assert any("total_gastos" in p for p in problemas), problemas


def test_detecta_un_saldo_que_no_cuadra(client, engine):
    _con_datos(client)
    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        original = verificacion.resumen_de(s)
    copia = {
        **original,
        "saldos": {k: float(v) - 1000 for k, v in original["saldos"].items()},
    }
    problemas = verificacion.comparar(original, copia)
    assert any("saldo" in p and "no cuadra" in p for p in problemas)


def test_detecta_una_tabla_que_no_llego(client, engine):
    _con_datos(client)
    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        original = verificacion.resumen_de(s)
    copia = {**original, "tablas": {k: v for k, v in original["tablas"].items() if k != "pagos"}}
    problemas = verificacion.comparar(original, copia)
    assert any("Falta la tabla pagos" in p for p in problemas)


def test_las_lecturas_de_ia_tambien_cuentan(client, engine):
    """Lo que se cobra y lo que cuesta tiene que viajar con la copia."""
    _, h = _registrar(client, email="u@example.com")
    with engine.begin() as conn:
        from sqlalchemy import text as sql_text

        conn.execute(
            sql_text(
                "insert into consumos_ia (id, usuario_id, periodo, lecturas, consultas, costo_usd) "
                "select gen_random_uuid(), id, '2026-09', 7, 3, 0.012 from usuarios where email = :e"
            ),
            {"e": "u@example.com"},
        )
    sf = sessionmaker(bind=engine)
    with sf.begin() as s:
        resumen = verificacion.resumen_de(s)
    assert resumen["dinero"]["lecturas_ia"] == 7
    huella = resumen["huellas"]["consumos_ia"]
    assert isinstance(huella, str) and len(huella) == 32, "la huella es un md5"
