"""Fase 4: valor acumulado (compromiso futuro, costo del dinero, auditoría y simulador).

Lo que se prueba, con las cifras reales que salieron de los extractos:

- el **compromiso futuro** por cuotas, mes a mes y **por moneda** (nunca se convierte);
- el **último estado de cada compra** manda: tener dos cortes no puede contar el capital dos veces;
- la **tasa real** es la ponderada por capital pendiente (la deuda cara pesa más);
- el **simulador** la usa, y si no hay tasa lo dice en vez de inventarla;
- el **costo del dinero** y qué parte de lo que pagas se va en eso;
- la **auditoría** extracto↔Konta: lo importado contra el pago mínimo del corte.
"""

from __future__ import annotations

import io
from decimal import Decimal

from test_api import _registrar

CERO = Decimal("0")


def _excel(
    filas: list[tuple[str, str, str, str, str, str, str]],
    moneda: str = "COP",
    pago_minimo: str = "1.000,00",
) -> bytes:
    """Extracto de Excel con las columnas del Amex (incluidas las de interés).

    `filas`: (fecha, descripción, valor, cuotas, cuota_mes, pendiente, tasa_anual_pct)
    """
    import openpyxl

    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = moneda
    hoja.append(["Información Cliente:"])
    hoja.append(["Moneda:", moneda])
    hoja.append(["Periodo facturado", "17 ago / 15 sep. 2026"])
    hoja.append(["Pago mínimo", pago_minimo])
    hoja.append(["Cupo total", "10.000.000,00"])
    hoja.append(["Tienes disponible", "9.000.000,00"])
    hoja.append([])
    hoja.append(["Movimientos durante el periodo"])
    hoja.append(
        ["Número de autorización", "Fecha", "Movimientos", "Valor Movimiento",
         "Número de cuotas", "Valor cuota/abono", "Interés mensual (%)",
         "Interés anual (%)", "Saldo pendiente"]
    )
    for fecha, desc, valor, cuotas, cuota_mes, pendiente, tasa in filas:
        hoja.append(["1", fecha, desc, valor, cuotas, cuota_mes, "", tasa, pendiente])
    buffer = io.BytesIO()
    libro.save(buffer)
    return buffer.getvalue()


def _subir(client, h, contenido: bytes, nombre: str = "extracto.xlsx", **campos):
    return client.post(
        "/extractos",
        headers=h,
        files={
            "archivo": (
                nombre,
                contenido,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data=campos,
    )


def test_proyeccion_de_cuotas_por_moneda(client):
    """Lo que ya compraste a cuotas: cuánto toca cada mes, sin mezclar monedas."""
    _, h = _registrar(client)
    contenido = _excel([
        ("15/09/2026", "TELEVISOR", "2.400.000,00", "3/24", "100.000,00", "2.100.000,00", "26,30"),
        ("20/09/2026", "LAVADORA", "1.200.000,00", "1/12", "100.000,00", "1.100.000,00", "24,00"),
    ])
    _subir(client, h, contenido)

    p = client.get("/extractos/proyeccion?meses=6", headers=h).json()
    cop = p["por_moneda"]["COP"]
    assert Decimal(cop["pendiente"]) == Decimal("3200000.00")
    assert Decimal(cop["cuota_mensual_actual"]) == Decimal("200000.00")
    assert cop["compras"] == 2
    # El televisor (21 cuotas por delante) cubre los 6 meses; la lavadora también
    assert Decimal(cop["meses"][p["meses"][0]]) == Decimal("200000.00")
    assert Decimal(cop["meses"][p["meses"][5]]) == Decimal("200000.00")

    # La proyección suma exactamente el capital pendiente que queda por pagar
    largo = client.get("/extractos/proyeccion?meses=24", headers=h).json()
    suma = sum(Decimal(v) for v in largo["por_moneda"]["COP"]["meses"].values())
    assert suma == Decimal("3200000.00"), "las cuotas que faltan suman el capital pendiente"
    assert Decimal(largo["por_moneda"]["COP"]["meses"][largo["meses"][-1]]) == CERO
    detalle = {d["descripcion"]: d for d in p["detalle"]}
    assert detalle["TELEVISOR"]["cuotas"] == "3/24"
    assert detalle["TELEVISOR"]["cuotas_restantes"] == 21
    assert detalle["TELEVISOR"]["tasa_ea"] == "0.2630"


def test_el_ultimo_corte_manda_en_cada_compra(client):
    """Con dos extractos, el capital pendiente de una compra no se cuenta dos veces."""
    _, h = _registrar(client)
    primero = _subir(client, h, _excel([
        ("15/08/2026", "TELEVISOR", "2.400.000,00", "2/24", "100.000,00", "2.200.000,00", "26,30"),
    ]))
    assert primero.status_code == 201
    # La compra conserva su **fecha de compra** en los dos cortes (es su identidad)
    segundo = _subir(client, h, _excel([
        ("15/08/2026", "TELEVISOR", "2.400.000,00", "3/24", "100.000,00", "2.100.000,00", "26,30"),
    ]))
    assert segundo.status_code == 201

    p = client.get("/extractos/proyeccion", headers=h).json()
    assert p["por_moneda"]["COP"]["compras"] == 1, "es la misma compra vista en dos cortes"
    assert Decimal(p["por_moneda"]["COP"]["pendiente"]) == Decimal("2100000.00"), "el más reciente"


def test_la_tasa_real_es_la_ponderada_por_capital(client):
    """La deuda cara pesa más: 100 al 20 % y 300 al 40 % dan 35 %."""
    _, h = _registrar(client)
    _subir(client, h, _excel([
        ("15/09/2026", "COMPRA BARATA", "100.000,00", "1/12", "10.000,00", "100.000,00", "20,00"),
        ("16/09/2026", "COMPRA CARA", "300.000,00", "1/12", "30.000,00", "300.000,00", "40,00"),
    ]))
    sim = client.get("/extractos/simulador", headers=h).json()
    assert Decimal(sim["tasa_ea"]) == Decimal("0.35")
    assert sim["fuente_de_la_tasa"] == "ponderada del extracto"
    assert Decimal(sim["saldo"]) == Decimal("400000.00")


def test_el_simulador_usa_la_tasa_de_la_tarjeta_si_el_extracto_no_la_trae(client):
    """Si el extracto no trae tasa se usa la de la tarjeta, y se dice que es esa."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas",
        headers=h,
        json={"nombre": "Visa", "tipo": "credito", "tasa_interes_ea": "0.30"},
    ).json()
    # La tarjeta se le asigna al extracto: es de donde sale la tasa de respaldo
    _subir(client, h, _excel([
        ("15/09/2026", "COMPRA SIN TASA", "1.000.000,00", "1/12", "100.000,00", "1.000.000,00", ""),
    ]), tarjeta_id=tarjeta["id"])

    sim = client.get("/extractos/simulador", headers=h).json()
    assert Decimal(sim["tasa_ea"]) == Decimal("0.30")
    assert sim["fuente_de_la_tasa"] == "configurada en la tarjeta"

    # Y sin tarjeta ni tasa, lo dice en vez de inventarla
    _, h2 = _registrar(client)
    _subir(client, h2, _excel([
        ("15/09/2026", "COMPRA SIN TASA", "1.000.000,00", "1/12", "100.000,00", "1.000.000,00", ""),
    ]))
    vacio = client.get("/extractos/simulador", headers=h2).json()
    assert vacio["tasa_ea"] is None
    assert "no la trae" in vacio["aviso"]


def test_el_simulador_dice_cuando_el_pago_no_alcanza(client):
    """Un pago que no cubre los intereses: la deuda nunca baja, y se avisa."""
    _, h = _registrar(client)
    _subir(client, h, _excel([
        ("15/09/2026", "COMPRA", "1.000.000,00", "1/12", "10.000,00", "1.000.000,00", "60,00"),
    ]))
    sim = client.get("/extractos/simulador?pago_mensual=1000", headers=h).json()
    assert sim["viable"] is False
    assert sim["meses"] == 0


def test_costo_del_dinero(client):
    """Intereses y comisiones del corte, y qué parte del pago se va en eso."""
    _, h = _registrar(client)
    contenido = _excel([
        ("15/09/2026", "INTERESES CORRIENTES", "156.600,42", "", "", "", ""),
        ("15/09/2026", "CUOTA DE MANEJO", "50.960,00", "", "", "", ""),
        ("11/09/2026", "AMAZON.COM", "24.900,00", "1/1", "24.900,00", "0,00", ""),
    ])
    _subir(client, h, contenido)
    costos = client.get("/extractos/costos", headers=h).json()
    total = Decimal(costos["total_por_moneda"]["COP"])
    assert total == Decimal("207560.42"), "156.600,42 + 50.960,00"
    fila = costos["extractos"][0]
    assert Decimal(fila["costo"]) == total
    # El pago mínimo del extracto de prueba son 1.000, así que el costo lo supera
    assert fila["porcentaje_del_pago"] is not None


def test_auditoria_extracto_konta(client):
    """Lo que el corte manda pagar contra lo que hay registrado."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas", headers=h, json={"nombre": "Amex", "tipo": "credito"}
    ).json()
    extracto = _subir(client, h, _excel(
        [("11/09/2026", "AMAZON.COM", "24.900,00", "1/1", "24.900,00", "0,00", "")],
        pago_minimo="24.900,00",
    ), tarjeta_id=tarjeta["id"]).json()

    # Sin importar: falta por importar
    antes = client.get(f"/extractos/{extracto['id']}/auditoria", headers=h).json()
    falta = next(x for x in antes if x["nombre"].startswith("todo lo que hay que importar"))
    assert falta["ok"] is False

    client.post(
        f"/extractos/{extracto['id']}/importar", headers=h, json={"tarjeta_id": tarjeta["id"]}
    )
    despues = client.get(f"/extractos/{extracto['id']}/auditoria", headers=h).json()
    assert {x["nombre"] for x in despues} >= {
        "lo que se importa cuadra con el pago mínimo del corte",
        "todo lo que hay que importar está importado",
        "no hay movimientos repetidos en el periodo",
        "el detalle cuadra con lo que declara el banco",
    }
    assert all(x["ok"] is not False for x in despues), despues


def test_la_auditoria_ve_los_movimientos_a_mano(client):
    """Un gasto del mismo periodo que no viene del extracto se señala."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas", headers=h, json={"nombre": "Amex", "tipo": "credito"}
    ).json()
    extracto = _subir(client, h, _excel(
        [("11/09/2026", "AMAZON.COM", "24.900,00", "1/1", "24.900,00", "0,00", "")],
        pago_minimo="24.900,00",
    ), tarjeta_id=tarjeta["id"]).json()
    client.post(
        f"/extractos/{extracto['id']}/importar", headers=h, json={"tarjeta_id": tarjeta["id"]}
    )
    # Un movimiento a mano dentro del periodo del extracto
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "1000", "fecha": "2026-09-12",
        "descripcion": "A MANO", "tarjeta_id": tarjeta["id"],
    })

    auditoria = client.get(f"/extractos/{extracto['id']}/auditoria", headers=h).json()
    repetidos = next(x for x in auditoria if x["nombre"].startswith("no hay movimientos repetidos"))
    assert "1 movimiento(s)" in repetidos["detalle"]
    assert repetidos["sugerencia"] is not None
