"""Fase 3: detectar recurrentes y suscripciones en los extractos.

Las reglas que se prueban son las que salieron de los datos reales:

- una compra **a cuotas nunca** es una suscripción (RAPPI aparece 7 veces a 24 cuotas);
- la señal fuerte es la **repetición entre cortes** (mismo comercio, ~1 mes, monto parecido);
- el **diccionario** salva al que aparece por primera vez (una suscripción nueva sale una
  sola vez en su primer extracto);
- dos cargos del mismo servicio el mismo día son **dos planes**, no uno doble;
- si el banco **difiere** una suscripción a cuotas, se propone con la cuota como monto.
"""

from __future__ import annotations

import io
from decimal import Decimal

from test_api import _registrar


def _excel(filas: list[tuple[str, str, str]], periodo: str = "17 ago / 15 sep. 2026") -> bytes:
    """Un extracto de Excel de una hoja con los movimientos que se le pasen."""
    import openpyxl

    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "PESOS"
    hoja.append(["Información Cliente:"])
    hoja.append(["Moneda:", "COP"])
    hoja.append(["Periodo facturado", periodo])
    hoja.append(["Pago mínimo", "10.000,00"])
    hoja.append([])
    hoja.append(["Movimientos durante el periodo"])
    hoja.append(
        ["Número de autorización", "Fecha", "Movimientos", "Valor Movimiento",
         "Número de cuotas", "Valor cuota/abono", "Saldo pendiente"]
    )
    for fecha, descripcion, valor, cuotas, cuota_mes in filas:
        hoja.append(["1", fecha, descripcion, valor, cuotas, cuota_mes, "0,00"])
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


def _candidatos(client, h, extracto_id: str):
    r = client.get(f"/extractos/{extracto_id}/recurrentes", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _por_nombre(candidatos, nombre: str):
    return [c for c in candidatos if nombre.lower() in c["nombre"].lower()]


def test_la_repeticion_entre_cortes_es_la_senal_fuerte(client):
    """El mismo comercio en dos extractos, a un mes y con el mismo monto."""
    _, h = _registrar(client)
    primero = _subir(
        client, h,
        _excel([("15/08/2026", "SPOTIFY COLOMBIA", "24.900,00", "1/1", "24.900,00")]),
        periodo="17 jul / 15 ago 2026",
    ).json()
    segundo = _subir(
        client, h,
        _excel([("15/09/2026", "SPOTIFY COLOMBIA", "24.900,00", "1/1", "24.900,00")]),
    ).json()

    candidatos = _candidatos(client, h, segundo["id"])
    spotify = _por_nombre(candidatos, "Spotify")
    assert len(spotify) == 1, candidatos
    assert spotify[0]["confianza"] == "alta"
    assert spotify[0]["monto"] == "24900.00"
    assert spotify[0]["periodicidad"] == "mensual"
    assert spotify[0]["apariciones"] == 2
    assert spotify[0]["proximo_pago"] == "2026-10-15"
    assert any("2 veces" in s for s in spotify[0]["senales"])
    # Aparece en este extracto y en el otro
    assert spotify[0]["en_este_extracto"] is True
    assert primero["id"] != segundo["id"]


def test_una_compra_a_cuotas_nunca_es_una_suscripcion(client):
    """El caso RAPPI: aparece muchas veces, pero es una compra a 24 cuotas."""
    _, h = _registrar(client)
    filas = [
        ("15/08/2026", "RAPPI", "121.900,00", "24/24", "5.079,16"),
        ("20/08/2026", "RAPPI", "121.900,00", "24/24", "5.079,16"),
        ("15/09/2026", "RAPPI", "121.900,00", "24/24", "5.079,16"),
        ("20/09/2026", "RAPPI", "121.900,00", "24/24", "5.079,16"),
    ]
    extracto = _subir(client, h, _excel(filas)).json()
    candidatos = _candidatos(client, h, extracto["id"])
    assert _por_nombre(candidatos, "Rappi") == [], "una compra a cuotas no es un recurrente"


def test_el_diccionario_salva_al_que_aparece_por_primera_vez(client):
    """Una suscripción nueva sale una sola vez en su primer extracto."""
    _, h = _registrar(client)
    extracto = _subir(
        client, h,
        _excel([("02/09/2026", "DLO*NETFLIX.COM", "44.900,00", "1/1", "44.900,00")]),
    ).json()
    netflix = _por_nombre(_candidatos(client, h, extracto["id"]), "Netflix")
    assert len(netflix) == 1
    assert netflix[0]["confianza"] == "media"
    assert any("cobro periódico" in s for s in netflix[0]["senales"])


def test_dos_cargos_del_mismo_servicio_el_mismo_dia_son_dos_planes(client):
    """PRIME VIDEO 17.999 y 4.999 el mismo día: son dos planes, no 22.998."""
    _, h = _registrar(client)
    extracto = _subir(
        client, h,
        _excel([
            ("11/09/2026", "PRIME VIDEO DL", "17.999,00", "1/1", "17.999,00"),
            ("11/09/2026", "PRIME VIDEO DL", "4.999,00", "1/1", "4.999,00"),
        ]),
    ).json()
    planes = _por_nombre(_candidatos(client, h, extracto["id"]), "Prime Video")
    assert sorted(c["monto"] for c in planes) == ["17999.00", "4999.00"]


def test_una_suscripcion_diferida_por_el_banco_se_propone_con_la_cuota(client):
    """Amex difiere AUDIBLE a 36 cuotas de 0,29 USD: al mes pagas la cuota."""
    _, h = _registrar(client)
    extracto = _subir(
        client, h,
        _excel([("02/09/2026", "AUDIBLE*536Y17LP1", "10,54", "1/36", "0,29")]),
    ).json()
    audible = _por_nombre(_candidatos(client, h, extracto["id"]), "Audible")
    assert len(audible) == 1
    assert audible[0]["monto"] == "0.29"
    assert any("difirió" in s for s in audible[0]["senales"])


def test_los_pagos_y_las_comisiones_no_son_recurrentes(client):
    _, h = _registrar(client)
    extracto = _subir(
        client, h,
        _excel([
            ("04/09/2026", "ABONO SUCURSAL VIRTUAL", "-974.993,00", "", ""),
            ("15/09/2026", "CUOTA DE MANEJO", "50.960,00", "", ""),
            ("15/09/2026", "INTERESES CORRIENTES", "156.600,42", "", ""),
            ("15/09/2026", "IMPUESTO 4X1000 GMF", "1.200,00", "", ""),
        ]),
    ).json()
    assert _candidatos(client, h, extracto["id"]) == []


def test_lo_que_ya_esta_en_el_historial_tambien_cuenta(client):
    """Con un solo extracto, los movimientos de otros meses son la repetición."""
    _, h = _registrar(client)
    hoy_ = __import__("datetime").date.today()
    for meses in (4, 3, 2):
        mes = hoy_.replace(day=15) - __import__("datetime").timedelta(days=30 * meses)
        client.post(
            "/transacciones",
            headers=h,
            json={
                "tipo": "gasto", "monto": "32.900", "fecha": mes.isoformat(),
                "descripcion": "WIN SPORTS",
            },
        )
    extracto = _subir(
        client, h, _excel([("15/09/2026", "WIN SPORTS", "32.900,00", "1/1", "32.900,00")])
    ).json()
    win = _por_nombre(_candidatos(client, h, extracto["id"]), "Win")
    assert len(win) == 1
    assert win[0]["confianza"] in ("alta", "media")
    assert any("ya estaba en tus movimientos" in s for s in win[0]["senales"])


def test_crear_los_recurrentes_elegidos(client):
    """Se eligen por clave y el servidor los crea desde sus propios datos."""
    _, h = _registrar(client)
    tarjeta = client.post(
        "/tarjetas", headers=h, json={"nombre": "Amex", "tipo": "credito"}
    ).json()
    extracto = _subir(
        client, h, _excel([("02/09/2026", "DLO*NETFLIX.COM", "44.900,00", "1/1", "44.900,00")]),
        tarjeta_id=tarjeta["id"],
    ).json()
    candidatos = _candidatos(client, h, extracto["id"])
    clave = candidatos[0]["clave"]

    r = client.post(
        f"/extractos/{extracto['id']}/recurrentes",
        headers=h,
        json={"claves": [clave]},
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert [s["nombre"] for s in datos["creadas"]] == ["Netflix"]
    assert datos["omitidas"] == []

    creada = datos["creadas"][0]
    assert Decimal(str(creada["monto"])) == Decimal("44900.00")
    assert creada["periodicidad"] == "mensual"
    assert creada["proximo_pago"] == "2026-10-02"
    assert creada["tarjeta_id"] == tarjeta["id"], "hereda la tarjeta del extracto"
    assert "Detectado en el extracto" in creada["notas"]

    # Ya está en recurrentes: no se duplica y el candidato lo dice
    otra = client.post(
        f"/extractos/{extracto['id']}/recurrentes", headers=h, json={"claves": [clave]}
    ).json()
    assert otra["creadas"] == []
    assert any("ya estaba" in m for m in otra["omitidas"])
    assert _candidatos(client, h, extracto["id"])[0]["ya_es_suscripcion"] is True
    assert len(client.get("/suscripciones", headers=h).json()) == 1


def test_una_clave_desconocida_no_crea_nada(client):
    _, h = _registrar(client)
    extracto = _subir(
        client, h, _excel([("02/09/2026", "DLO*NETFLIX.COM", "44.900,00", "1/1", "44.900,00")])
    ).json()
    r = client.post(
        f"/extractos/{extracto['id']}/recurrentes", headers=h, json={"claves": ["inventada|1"]}
    ).json()
    assert r["creadas"] == []
    assert len(r["omitidas"]) == 1
