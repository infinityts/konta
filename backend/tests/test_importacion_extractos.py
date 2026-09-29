"""Fase 2: importar los movimientos del extracto a Konta.

Las reglas son las que decidió el usuario, así que aquí se prueban una por una:

- la **cuota del mes** es el gasto (una compra a 24 cuotas no es un gasto de una vez);
- los **ajustes** no se importan (suman y restan lo mismo);
- solo el **periodo** (lo anterior ya estaba contado el mes en que se compró);
- los **pagos** tampoco son un gasto (pagar lo tuyo no es gastar);
- y nada se inventa: si falta la cuota del mes, la fila no se importa y se dice por qué.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from test_api import _registrar
from test_extractos import _excel_amex

from app.importacion_extractos import (
    MOTIVO_AJUSTE,
    MOTIVO_CUOTA_ANTERIOR,
    MOTIVO_INFORMATIVO,
    MOTIVO_PAGO,
    MOTIVO_SIN_CUOTA,
    MOTIVO_YA_IMPORTADO,
    comparar_con_el_pago_minimo,
    plan_de_importacion,
    resumen_del_plan,
)


class _Extracto:
    """Un extracto de mentira con las cifras que declara el corte."""

    def __init__(self, **campos):
        self.intereses = Decimal(str(campos["intereses"])) if campos.get("intereses") else None
        self.intereses_mora = None
        self.otros_cargos = None
        self.pago_minimo = Decimal(str(campos["pago_minimo"])) if campos.get("pago_minimo") else None
        self.moneda = campos.get("moneda", "COP")
        self.fecha_corte = campos.get("fecha_corte", date(2026, 8, 28))


class _Mov:
    """Un movimiento de extracto de mentira, con lo justo para el plan."""

    def __init__(self, **campos):
        self.id = uuid.uuid4()
        self.fecha = campos.get("fecha", date(2026, 9, 10))
        self.descripcion = campos.get("descripcion", "COMPRA")
        self.valor = Decimal(str(campos.get("valor", "1000")))
        self.moneda = campos.get("moneda", "COP")
        self.tipo = campos.get("tipo", "compra")
        self.cuotas_n = campos.get("cuotas_n")
        self.cuotas_total = campos.get("cuotas_total")
        self.cuota_mes = (
            Decimal(str(campos["cuota_mes"])) if campos.get("cuota_mes") is not None else None
        )
        self.valor_pendiente = None
        self.es_informativo = campos.get("es_informativo", False)
        self.transaccion_id = campos.get("transaccion_id")
        self.categoria_id = None
        self.etiqueta_id = None


def test_la_cuota_del_mes_es_el_gasto():
    """La regla central: una compra a 24 cuotas gasta la cuota, no el valor entero."""
    plan = plan_de_importacion(
        [
            _Mov(descripcion="TELEVISOR", valor="2400000", cuotas_n=3, cuotas_total=24,
                 cuota_mes="100000"),
            _Mov(descripcion="MERCADO", valor="85000"),
        ]
    )
    assert [x.monto for x in plan] == [Decimal("100000.00"), Decimal("85000.00")]
    assert all(x.incluir for x in plan)
    # La descripción deja rastro de que es una cuota
    assert "cuota 3/24" in plan[0].descripcion
    # Y el valor de la compra queda a la vista, para poder auditar
    assert plan[0].valor_compra == Decimal("2400000.00")


def test_los_ajustes_y_los_pagos_no_se_importan():
    plan = plan_de_importacion(
        [
            _Mov(descripcion="AJUSTE PAGO MIN ALTO", valor="772653.02", tipo="ajuste"),
            _Mov(descripcion="PAGO TARJETA", valor="-612126", tipo="pago"),
            _Mov(descripcion="COMPRA BUENA", valor="1000"),
        ]
    )
    assert plan[0].motivo == MOTIVO_AJUSTE
    assert plan[1].motivo == MOTIVO_PAGO
    assert plan[2].incluir is True
    assert resumen_del_plan(plan)["se_importan"] == 1


def test_una_compra_vieja_de_una_sola_cuota_no_se_importa():
    """Su valor ya se contó cuando se compró: importarlo sería contarlo dos veces."""
    plan = plan_de_importacion(
        [_Mov(descripcion="COMPRA VIEJA", es_informativo=True, cuotas_n=1, cuotas_total=1)]
    )
    assert plan[0].motivo == MOTIVO_INFORMATIVO
    assert plan[0].incluir is False


def test_la_cuota_de_una_compra_vieja_si_se_importa():
    """Se paga **este** mes: es lo que hace que el mes cuadre con el pago mínimo.

    En el extracto real de Davivienda, 84.877,19 de las compras del periodo +
    170.575,21 de las anteriores + 97.624,49 de intereses = 353.076,89: el pago mínimo
    exacto. Si se saltaran las cuotas anteriores, faltarían esos 170.575,21.
    """
    plan = plan_de_importacion(
        [
            _Mov(
                descripcion="RAPPI VIEJA",
                valor="121900",
                es_informativo=True,
                cuotas_n=5,
                cuotas_total=24,
                cuota_mes="5079.16",
            )
        ]
    )
    assert plan[0].incluir is True
    assert plan[0].monto == Decimal("5079.16")
    assert plan[0].de_meses_anteriores is True
    resumen = resumen_del_plan(plan)
    assert Decimal(resumen["de_meses_anteriores"]) == Decimal("5079.16")


def test_se_puede_dejar_fuera_las_cuotas_anteriores():
    plan = plan_de_importacion(
        [
            _Mov(
                descripcion="RAPPI VIEJA",
                es_informativo=True,
                cuotas_n=5,
                cuotas_total=24,
                cuota_mes="5079.16",
            )
        ],
        incluir_cuotas_anteriores=False,
    )
    assert plan[0].motivo == MOTIVO_CUOTA_ANTERIOR
    assert plan[0].incluir is False


def test_los_intereses_que_declara_el_corte_se_importan_si_no_son_movimiento():
    """Davivienda declara 97.624,49 de intereses que no están en su tabla.

    Sin esa línea el mes no cuadra con el pago mínimo; con ella, sí. Y si el banco **sí**
    los lista (Amex), no se añade nada para no contarlos dos veces.
    """
    extracto = _Extracto(intereses="97624.49", pago_minimo="353076.89", moneda="COP")
    plan = plan_de_importacion(
        [_Mov(valor="84877.19", cuota_mes="84877.19", cuotas_n=1, cuotas_total=24)], extracto
    )
    sintetica = [x for x in plan if x.sintetica]
    assert len(sintetica) == 1
    assert sintetica[0].monto == Decimal("97624.49")
    assert sintetica[0].tipo == "interes"

    # Con los intereses ya como movimiento, no se duplican
    con_movimiento = plan_de_importacion(
        [
            _Mov(valor="84877.19", cuota_mes="84877.19", cuotas_n=1, cuotas_total=24),
            _Mov(descripcion="INTERESES CORRIENTES", valor="97624.49", tipo="interes"),
        ],
        extracto,
    )
    assert [x for x in con_movimiento if x.sintetica] == []


def test_comparar_con_el_pago_minimo():
    """El pago mínimo del corte es la cifra con la que tiene que cuadrar el mes."""
    extracto = _Extracto(pago_minimo="353076.89", moneda="COP")
    resumen = {"gastos_por_moneda": {"COP": "353076.89"}}
    diferencia, nota = comparar_con_el_pago_minimo(resumen, extracto)
    assert diferencia == Decimal("0")
    assert "coincide con el pago mínimo" in nota

    # Cuando no cuadra se dice, no se disimula
    resumen = {"gastos_por_moneda": {"COP": "100"}}
    diferencia, nota = comparar_con_el_pago_minimo(resumen, extracto)
    assert diferencia == Decimal("352976.89")
    assert "Revísalo" in nota

    # Sin pago mínimo declarado no se inventa una comparación
    assert comparar_con_el_pago_minimo(resumen, _Extracto()) == (None, None)


def test_no_se_importa_dos_veces():
    plan = plan_de_importacion([_Mov(descripcion="YA ESTABA", transaccion_id=uuid.uuid4())])
    assert plan[0].motivo == MOTIVO_YA_IMPORTADO
    assert plan[0].ya_importado is True
    assert plan[0].incluir is False


def test_sin_la_cuota_del_mes_no_se_inventa_nada():
    """Ni el valor completo (inflaría el mes) ni la mitad: no se importa y se explica."""
    plan = plan_de_importacion(
        [_Mov(descripcion="A CUOTAS SIN CUOTA", valor="1200000", cuotas_n=1, cuotas_total=24)]
    )
    assert plan[0].motivo == MOTIVO_SIN_CUOTA
    assert plan[0].incluir is False


def test_la_nomina_es_un_ingreso():
    plan = plan_de_importacion(
        [_Mov(descripcion="NOMINA SEPTIEMBRE", valor="4500000", tipo="nomina")]
    )
    assert plan[0].incluir is True
    assert plan[0].es_gasto is False
    resumen = resumen_del_plan(plan)
    assert Decimal(resumen["ingresos_por_moneda"]["COP"]) == Decimal("4500000")
    assert resumen["gastos_por_moneda"] == {}


def test_resumen_por_moneda():
    plan = plan_de_importacion(
        [
            _Mov(valor="1000", moneda="COP"),
            _Mov(valor="10.54", moneda="USD"),
        ]
    )
    resumen = resumen_del_plan(plan)
    assert resumen["se_importan"] == 2
    assert Decimal(resumen["gastos_por_moneda"]["COP"]) == Decimal("1000")
    assert Decimal(resumen["gastos_por_moneda"]["USD"]) == Decimal("10.54")


def _subir(client, h, contenido: bytes = None, nombre: str = "extracto.xlsx", **campos):
    return client.post(
        "/extractos",
        headers=h,
        files={
            "archivo": (
                nombre,
                contenido if contenido is not None else _excel_amex(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        data=campos,
    )


def test_previsualizar_y_importar(client):
    """De punta a punta: previsualizar, importar, y no poder duplicar."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas", headers=h, json={"nombre": "Visa", "tipo": "credito"}
    ).json()
    extracto = _subir(client, h, tarjeta_id=tarjeta["id"]).json()

    # --- previsualización: mismas reglas que la importación ---
    previa = client.get(f"/extractos/{extracto['id']}/importar", headers=h).json()
    # Se importan las 2 compras del periodo y las 2 cuotas de las compras de meses
    # anteriores (que también se pagan este mes); los 2 pagos se omiten
    assert previa["resumen"]["se_importan"] == 4, previa["resumen"]
    assert previa["resumen"]["se_omiten"] == 2, previa["resumen"]
    assert Decimal(previa["resumen"]["de_meses_anteriores"]) == Decimal("73069.60")
    assert len(previa["resumen"]["gastos_por_moneda"]) == 2
    assert Decimal(previa["resumen"]["gastos_por_moneda"]["COP"]) == Decimal("97943.53")
    assert Decimal(previa["resumen"]["gastos_por_moneda"]["USD"]) == Decimal("36.61")
    # Lo único que se omite son los pagos, y se dice por qué
    assert [m for m in previa["resumen"]["motivos"]] == [MOTIVO_PAGO]

    # --- importar ---
    r = client.post(
        f"/extractos/{extracto['id']}/importar",
        headers=h,
        json={"tarjeta_id": tarjeta["id"]},
    )
    assert r.status_code == 200, r.text
    resultado = r.json()
    assert resultado["creadas"] == 4
    assert Decimal(resultado["gastos_por_moneda"]["COP"]) == Decimal("97943.53")
    assert resultado["pago_minimo"] is not None
    assert resultado["nota_pago_minimo"]

    # Cada movimiento importado queda enlazado a su transacción
    detalle = client.get(f"/extractos/{extracto['id']}", headers=h).json()
    importados = [m for m in detalle["movimientos"] if m["transaccion_id"] is not None]
    assert len(importados) == 4

    # Y las transacciones existen con su tarjeta y su moneda
    transacciones = client.get("/transacciones", headers=h).json()
    assert len(transacciones) == 4
    assert {t["moneda"] for t in transacciones} == {"COP", "USD"}
    usd = next(t for t in transacciones if t["moneda"] == "USD")
    assert Decimal(str(usd["monto"])) == Decimal("10.54")
    assert all(t["tarjeta_id"] == tarjeta["id"] for t in transacciones)

    # --- pulsar otra vez no duplica ---
    otra = client.post(
        f"/extractos/{extracto['id']}/importar",
        headers=h,
        json={"tarjeta_id": tarjeta["id"]},
    ).json()
    assert otra["creadas"] == 0
    assert otra["se_importan"] == 0
    assert any(MOTIVO_YA_IMPORTADO in m for m in otra["motivos"])
    assert len(client.get("/transacciones", headers=h).json()) == 4


def test_importar_registra_la_deuda_del_corte(client):
    """Decisión del usuario: el **cupo utilizado** del corte es la deuda de la tarjeta."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas", headers=h, json={"nombre": "Amex", "tipo": "credito"}
    ).json()
    extracto = _subir(client, h, tarjeta_id=tarjeta["id"]).json()

    resultado = client.post(
        f"/extractos/{extracto['id']}/importar",
        headers=h,
        json={"tarjeta_id": tarjeta["id"]},
    ).json()
    # El extracto de prueba declara 1.000.000 de cupo y 750.000 disponibles
    assert Decimal(resultado["deuda_registrada"]) == Decimal("250000.00")

    tarjetas = client.get("/tarjetas", headers=h).json()
    deuda = next(t for t in tarjetas if t["id"] == tarjeta["id"])["deuda_por_moneda"]
    assert Decimal(str(deuda["COP"])) == Decimal("250000.0")


def test_el_extracto_alimenta_la_alerta_de_pago(client):
    """El **pago total** del corte es la obligación de pago, con la fecha del extracto."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas", headers=h, json={"nombre": "Amex", "tipo": "credito"}
    ).json()
    _subir(client, h, tarjeta_id=tarjeta["id"])

    alertas = client.get("/alertas", headers=h).json()
    pago = next((a for a in alertas if a["tipo"] == "tarjeta_pago"), None)
    assert pago is not None, alertas
    assert pago["origen"] == "extracto"
    assert Decimal(str(pago["monto"])) == Decimal("5000.00")
    assert pago["fecha"] is not None
