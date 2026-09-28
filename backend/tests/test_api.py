"""Tests de la API: auth, CRUD y aislamiento multi-usuario."""

import uuid
from datetime import date, timedelta


def _registrar(client, email: str | None = None):
    email = email or f"u{uuid.uuid4().hex[:8]}@x.com"
    r = client.post(
        "/auth/register",
        json={"email": email, "nombre": "Test", "password": "password123"},
    )
    assert r.status_code == 201, r.text
    token = client.post(
        "/auth/login", json={"email": email, "password": "password123"}
    ).json()["access_token"]
    return email, {"Authorization": f"Bearer {token}"}


def test_registro_y_login(client):
    email, _ = _registrar(client)
    assert email.endswith("@x.com")


def test_email_duplicado(client):
    email, _ = _registrar(client)
    r = client.post(
        "/auth/register",
        json={"email": email, "nombre": "Test", "password": "password123"},
    )
    assert r.status_code == 409


def test_sin_token_rechazado(client):
    assert client.get("/categorias").status_code == 401


def test_crud_categorias(client):
    _, h = _registrar(client)
    assert len(client.get("/categorias", headers=h).json()) == 10  # por defecto

    r = client.post("/categorias", headers=h, json={"nombre": "Mascotas", "tipo": "gasto"})
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.patch(f"/categorias/{cid}", headers=h, json={"color": "#000000"})
    assert r.json()["color"] == "#000000"

    assert client.delete(f"/categorias/{cid}", headers=h).status_code == 204
    assert len(client.get("/categorias", headers=h).json()) == 10


def test_flujo_tarjetas_suscripciones_transacciones(client):
    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    cat = next(x for x in cats if x["nombre"] == "Suscripciones")

    tar = client.post(
        "/tarjetas", headers=h,
        json={"nombre": "Visa", "tipo": "credito", "moneda": "COP", "dia_corte": 15, "dia_pago": 5},
    ).json()

    sub = client.post(
        "/suscripciones", headers=h,
        json={
            "nombre": "Netflix", "monto": "26000", "moneda": "COP",
            "periodicidad": "mensual", "proximo_pago": "2026-10-15",
            "categoria_id": cat["id"], "tarjeta_id": tar["id"],
        },
    ).json()

    tx = client.post(
        "/transacciones", headers=h,
        json={
            "tipo": "gasto", "monto": "26000", "moneda": "COP", "fecha": "2026-10-15",
            "descripcion": "Netflix", "categoria_id": cat["id"],
            "tarjeta_id": tar["id"], "suscripcion_id": sub["id"],
        },
    ).json()
    assert tx["tipo"] == "gasto"

    assert len(client.get("/tarjetas", headers=h).json()) == 1
    assert len(client.get("/suscripciones", headers=h).json()) == 1
    assert len(client.get("/transacciones", headers=h).json()) == 1


def test_aislamiento_multiusuario(client):
    _, h1 = _registrar(client, "a@x.com")
    _, h2 = _registrar(client, "b@x.com")

    tar = client.post("/tarjetas", headers=h1, json={"nombre": "Visa", "tipo": "credito"}).json()

    assert len(client.get("/tarjetas", headers=h2).json()) == 0
    assert client.get(f"/tarjetas/{tar['id']}", headers=h2).status_code == 404


def test_ingresos_recurrentes_crud(client):
    _, h = _registrar(client)

    r = client.post(
        "/ingresos-recurrentes", headers=h,
        json={"nombre": "Salario", "monto": "1000000", "periodicidad": "mensual", "dia": 15},
    )
    assert r.status_code == 201
    item = r.json()
    assert item["proxima_ejecucion"]

    # validación: mensual sin día -> 422
    r = client.post(
        "/ingresos-recurrentes", headers=h,
        json={"nombre": "Mal", "monto": "100", "periodicidad": "mensual"},
    )
    assert r.status_code == 422

    assert len(client.get("/ingresos-recurrentes", headers=h).json()) == 1
    assert client.delete(f"/ingresos-recurrentes/{item['id']}", headers=h).status_code == 204
    assert len(client.get("/ingresos-recurrentes", headers=h).json()) == 0


def test_etiquetas_y_subetiquetas(client):
    _, h = _registrar(client)

    # etiqueta raíz
    r = client.post("/etiquetas", headers=h, json={"nombre": "Trabajo"})
    assert r.status_code == 201
    root = r.json()
    assert root["padre_id"] is None

    # subetiqueta
    r = client.post("/etiquetas", headers=h, json={"nombre": "Reuniones", "padre_id": root["id"]})
    assert r.status_code == 201
    sub = r.json()
    assert sub["padre_id"] == root["id"]

    assert len(client.get("/etiquetas", headers=h).json()) == 2

    # transacción etiquetada con la subetiqueta
    tx = client.post(
        "/transacciones", headers=h,
        json={"tipo": "gasto", "monto": "5000", "fecha": "2026-09-27", "descripcion": "Almuerzo", "etiqueta_id": sub["id"]},
    ).json()
    assert tx["etiqueta_id"] == sub["id"]

    # borrar la raíz elimina la subetiqueta en cascada
    assert client.delete(f"/etiquetas/{root['id']}", headers=h).status_code == 204
    assert len(client.get("/etiquetas", headers=h).json()) == 0


def test_alertas_de_pagos(client):
    _, h = _registrar(client)
    hoy = date.today()

    # suscripción que vence en 3 días
    client.post(
        "/suscripciones", headers=h,
        json={"nombre": "Netflix", "monto": "26000", "periodicidad": "mensual", "proximo_pago": (hoy + timedelta(days=3)).isoformat()},
    )
    # tarjeta con día de pago y corte hoy
    client.post(
        "/tarjetas", headers=h,
        json={"nombre": "Visa", "tipo": "credito", "dia_pago": hoy.day, "dia_corte": hoy.day},
    )

    r = client.get("/alertas", headers=h)
    assert r.status_code == 200
    tipos = {a["tipo"] for a in r.json()}
    assert "suscripcion" in tipos
    assert "tarjeta_pago" in tipos
    assert "tarjeta_corte" in tipos


def test_reportes(client):
    _, h = _registrar(client)
    hoy = date.today()
    client.post("/transacciones", headers=h, json={"tipo": "ingreso", "monto": "1000", "fecha": hoy.isoformat(), "descripcion": "sueldo"})
    client.post("/transacciones", headers=h, json={"tipo": "gasto", "monto": "400", "fecha": hoy.isoformat(), "descripcion": "comida"})

    r = client.get("/reportes/mensual?meses=6", headers=h)
    assert r.status_code == 200
    datos = r.json()
    assert len(datos) == 6
    actual = datos[-1]
    assert actual["ingresos"] == 1000
    assert actual["gastos"] == 400
    assert actual["balance"] == 600

    r = client.get(f"/reportes/categorias?mes={hoy.strftime('%Y-%m')}", headers=h)
    assert r.status_code == 200
    assert any(c["tipo"] == "gasto" for c in r.json())


def _pdf_minimo(texto: str) -> bytes:
    """Construye un PDF mínimo válido con un texto (para probar la extracción)."""
    contenido = f"BT /F1 24 Tf 72 720 Td ({texto}) Tj ET".encode()
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(contenido)).encode() + b" >>\nstream\n" + contenido + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objetos, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objetos) + 1}\n".encode() + b"0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    return bytes(out)


def test_facturas_extraccion_y_subida(client):
    from app.facturas import detectar_fecha, detectar_monto

    assert str(detectar_monto("Total a pagar: 123.45")) == "123.45"
    assert str(detectar_fecha("Fecha: 2026-09-27")) == "2026-09-27"

    _, h = _registrar(client)
    pdf = _pdf_minimo("Factura Total: 250.00")
    r = client.post("/facturas", headers=h, files={"archivo": ("f.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["nombre_archivo"] == "f.pdf"
    assert f["monto_detectado"] is not None
    assert len(client.get("/facturas", headers=h).json()) == 1


def test_presupuestos(client):
    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    mercado = next(c for c in cats if c["nombre"] == "Mercado")
    hoy = date.today()

    # gasto de 300 en Mercado
    client.post("/transacciones", headers=h, json={"tipo": "gasto", "monto": "300", "fecha": hoy.isoformat(), "categoria_id": mercado["id"]})

    # presupuesto de 500 para Mercado
    r = client.post("/presupuestos", headers=h, json={"categoria_id": mercado["id"], "monto_limite": "500"})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["gastado"] == 300
    assert p["restante"] == 200
    assert p["porcentaje"] == 60.0

    assert len(client.get("/presupuestos", headers=h).json()) == 1


def test_importar_csv(client):
    _, h = _registrar(client)
    csv_txt = "fecha,descripcion,valor\n2026-09-20,Mercado,-50000\n2026-09-21,Salario,2000000\n"
    r = client.post(
        "/importar/csv", headers=h,
        files={"archivo": ("estado.csv", csv_txt.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["total"] == 2
    assert datos["filas"][0]["tipo"] == "gasto"    # monto negativo
    assert datos["filas"][1]["tipo"] == "ingreso"  # monto positivo

    r = client.post("/importar/confirmar", headers=h, json={"filas": datos["filas"]})
    assert r.status_code == 200
    assert r.json()["creadas"] == 2
    assert len(client.get("/transacciones", headers=h).json()) == 2


def test_mercado_comparativo_y_lista(client):
    _, h = _registrar(client)

    prod = client.post("/productos", headers=h, json={"nombre": "Leche", "unidad": "litro"}).json()
    client.post(f"/productos/{prod['id']}/precios", headers=h, json={"tienda": "Tienda A", "precio": "4000"})
    client.post(f"/productos/{prod['id']}/precios", headers=h, json={"tienda": "Tienda B", "precio": "3500"})

    comp = client.get(f"/productos/{prod['id']}/comparativo", headers=h).json()
    assert comp["mas_barata"] == "Tienda B"
    assert len(comp["tiendas"]) == 2
    assert comp["tiendas"][0]["tienda"] == "Tienda B"

    client.post("/lista-mercado", headers=h, json={"nombre": "Leche", "cantidad": "2", "precio_estimado": "3500"})
    lista = client.get("/lista-mercado", headers=h).json()
    assert len(lista["items"]) == 1
    assert lista["total_estimado"] == 7000.0
    assert lista["pendientes"] == 1


def test_monedas_y_tasas(client):
    _, h = _registrar(client)

    monedas = client.get("/monedas", headers=h).json()
    assert any(m["codigo"] == "COP" for m in monedas)

    r = client.post("/tasas", headers=h, json={"moneda_origen": "USD", "moneda_destino": "COP", "tasa": "4000"})
    assert r.status_code == 201, r.text

    r = client.get("/convertir", headers=h, params={"de": "USD", "a": "COP", "monto": 100})
    assert r.status_code == 200
    assert float(r.json()["resultado"]) == 400000.0

    # conversión inversa usando la tasa inversa
    r = client.get("/convertir", headers=h, params={"de": "COP", "a": "USD", "monto": 400000})
    assert r.status_code == 200
    assert abs(float(r.json()["resultado"]) - 100.0) < 0.01

    # sin tasa -> 404
    r = client.get("/convertir", headers=h, params={"de": "EUR", "a": "COP", "monto": 1})
    assert r.status_code == 404


def test_simulador_tarjeta(client):
    _, h = _registrar(client)
    tar = client.post("/tarjetas", headers=h, json={"nombre": "Visa", "tipo": "credito", "tasa_interes": "0.02"}).json()

    r = client.get(f"/tarjetas/{tar['id']}/simulador", headers=h, params={"saldo": 1000000, "pago_mensual": 200000})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["viable"] is True
    assert d["meses"] > 0
    assert float(d["total_intereses"]) > 0

    # pago que no cubre el interés del mes -> no viable
    d2 = client.get(f"/tarjetas/{tar['id']}/simulador", headers=h, params={"saldo": 1000000, "pago_mensual": 10000}).json()
    assert d2["viable"] is False

    # tarjeta sin tasa -> 400
    tar2 = client.post("/tarjetas", headers=h, json={"nombre": "Sin tasa", "tipo": "credito"}).json()
    assert client.get(f"/tarjetas/{tar2['id']}/simulador", headers=h, params={"saldo": 100}).status_code == 400


def test_exportar_y_restaurar(client):
    _, h = _registrar(client)
    cat = client.get("/categorias", headers=h).json()[0]
    client.post(
        "/transacciones", headers=h,
        json={"tipo": "gasto", "monto": "100", "fecha": "2026-09-27", "descripcion": "X", "categoria_id": cat["id"]},
    )

    # exportar JSON
    r = client.get("/exportar/json", headers=h)
    assert r.status_code == 200
    backup = r.json()
    assert len(backup["transacciones"]) == 1
    assert len(backup["categorias"]) == 10

    # borrar y restaurar
    client.delete(f"/transacciones/{backup['transacciones'][0]['id']}", headers=h)
    assert len(client.get("/transacciones", headers=h).json()) == 0

    import json as _json

    contenido = _json.dumps(backup).encode("utf-8")
    r = client.post(
        "/respaldar/restaurar", headers=h,
        files={"archivo": ("respaldo.json", contenido, "application/json")},
    )
    assert r.status_code == 200, r.text
    assert len(client.get("/transacciones", headers=h).json()) == 1
    assert len(client.get("/categorias", headers=h).json()) == 10

    # exportar CSV
    r = client.get("/exportar/transacciones.csv", headers=h)
    assert r.status_code == 200
    assert "fecha,tipo,monto" in r.text


def test_flujo_caja(client):
    _, h = _registrar(client)
    hoy = date.today()

    def mes_atras(n: int) -> date:
        y, m = hoy.year, hoy.month - n
        while m <= 0:
            m += 12
            y -= 1
        return date(y, m, 15)

    # 3 gastos variables (sin suscripción) en meses anteriores -> promedio 300.000
    for n in (1, 2, 3):
        client.post("/transacciones", headers=h, json={"tipo": "gasto", "monto": "300000", "fecha": mes_atras(n).isoformat()})

    client.post("/ingresos-recurrentes", headers=h, json={"nombre": "Sueldo", "monto": "1000000", "periodicidad": "mensual", "dia": 1})
    client.post("/suscripciones", headers=h, json={"nombre": "Netflix", "monto": "50000", "periodicidad": "mensual", "proximo_pago": hoy.isoformat()})

    r = client.get("/flujo-caja?meses=6", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["meses"]) == 6
    assert d["gasto_variable_promedio"] == 300000.0
    assert d["meses"][0]["gastos_variables"] == 300000.0
    assert d["meses"][0]["gastos_fijos"] == 50000.0
    assert d["meses"][0]["gastos"] == 350000.0
    assert d["total_ingresos"] > 0

    # el acumulado es la suma de los balances
    acum = 0.0
    for m in d["meses"]:
        acum += m["balance"]
        assert abs(m["acumulado"] - acum) < 0.01


def test_metas_ahorro(client):
    _, h = _registrar(client)

    m = client.post("/metas", headers=h, json={"nombre": "Viaje", "monto_objetivo": "1000000"}).json()
    assert m["monto_actual"] == 0.0
    assert m["porcentaje"] == 0.0
    assert m["completada"] is False
    assert m["aporte_mensual_sugerido"] is None

    client.post(f"/metas/{m['id']}/aportes", headers=h, json={"monto": "250000"})
    metas = client.get("/metas", headers=h).json()
    assert metas[0]["monto_actual"] == 250000.0
    assert metas[0]["restante"] == 750000.0
    assert metas[0]["porcentaje"] == 25.0

    client.post(f"/metas/{m['id']}/aportes", headers=h, json={"monto": "750000"})
    metas = client.get("/metas", headers=h).json()
    assert metas[0]["completada"] is True
    assert metas[0]["porcentaje"] == 100.0
    assert len(client.get(f"/metas/{m['id']}/aportes", headers=h).json()) == 2

    # con fecha límite -> aporte mensual sugerido
    futuro = (date.today() + timedelta(days=60)).isoformat()
    m2 = client.post("/metas", headers=h, json={"nombre": "Carro", "monto_objetivo": "600000", "fecha_limite": futuro}).json()
    assert m2["aporte_mensual_sugerido"] is not None


def test_notificaciones(client):
    _, h = _registrar(client)

    r = client.get("/notificaciones", headers=h)
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["activo"] is False
    assert cfg["dias_anticipacion"] == 5

    r = client.put(
        "/notificaciones", headers=h,
        json={"canal": "ambos", "telegram_chat_id": "999", "email": "yo@example.com", "dias_anticipacion": 3, "activo": True},
    )
    assert r.status_code == 200, r.text
    cfg = r.json()
    assert cfg["canal"] == "ambos"
    assert cfg["telegram_chat_id"] == "999"
    assert cfg["email"] == "yo@example.com"
    assert cfg["dias_anticipacion"] == 3
    assert cfg["activo"] is True

    # el mensaje incluye el título y el "hoy"
    from app.notificaciones import construir_mensaje

    texto = construir_mensaje(
        [{"fecha": date.today(), "dias_restantes": 0, "titulo": "Netflix", "monto": 50000, "moneda": "COP"}]
    )
    assert "Netflix" in texto
    assert "hoy" in texto

    # sin token/SMTP configurado -> 502 con detalle
    r = client.post("/notificaciones/probar", headers=h)
    assert r.status_code == 502

    # detectar sin token -> 400
    r = client.post("/notificaciones/telegram/detectar", headers=h)
    assert r.status_code == 400


def test_cuentas_saldos_y_subcategorias(client):
    _, h = _registrar(client)

    # cuenta con saldo inicial
    cta = client.post("/cuentas", headers=h, json={"nombre": "Banco", "tipo": "banco", "saldo_inicial": "1000000"}).json()
    assert cta["saldo_actual"] == 1000000.0

    # categoría raíz + subcategoría
    raiz = client.post("/categorias", headers=h, json={"nombre": "Transporte", "tipo": "gasto"}).json()
    sub = client.post("/categorias", headers=h, json={"nombre": "Gasolina", "tipo": "gasto", "padre_id": raiz["id"]}).json()
    assert sub["padre_id"] == raiz["id"]

    arbol = client.get("/categorias/arbol", headers=h).json()
    transp = next(n for n in arbol if n["nombre"] == "Transporte")
    assert any(s["nombre"] == "Gasolina" for s in transp["subcategorias"])

    hoy = date.today()
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "200000", "fecha": hoy.isoformat(),
        "categoria_id": sub["id"], "cuenta_id": cta["id"],
    })
    client.post("/transacciones", headers=h, json={
        "tipo": "ingreso", "monto": "500000", "fecha": hoy.isoformat(), "cuenta_id": cta["id"],
    })

    # saldo = 1.000.000 + 500.000 - 200.000
    r = client.get("/saldos", headers=h).json()
    assert r["saldo_total"] == 1300000.0
    assert r["sobregirado"] is False
    assert r["cuentas"][0]["saldo_actual"] == 1300000.0

    # desglose por categoría → subcategoría
    rep = client.get(f"/reportes/categorias?mes={hoy.strftime('%Y-%m')}", headers=h).json()
    gasto = next(x for x in rep if x["tipo"] == "gasto")
    assert gasto["categoria"] == "Transporte"
    assert gasto["subcategoria"] == "Gasolina"

    diag = client.get("/saldos/diagnostico", headers=h).json()
    assert diag["sobregirado"] is False
    assert diag["saldo_actual"] == 1300000.0
    assert any("Transporte" in m for m in diag["motivos"])

    cons = client.get("/saldos/consolidado?meses=3", headers=h).json()
    assert len(cons["meses"]) == 3
    assert cons["meses"][-1]["saldo_final"] == 1300000.0


def test_diagnostico_de_sobregiro(client):
    _, h = _registrar(client)
    cta = client.post("/cuentas", headers=h, json={"nombre": "Efectivo", "saldo_inicial": "100000"}).json()
    hoy = date.today()
    comida = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado")
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "300000", "fecha": hoy.isoformat(),
        "categoria_id": comida["id"], "cuenta_id": cta["id"],
    })

    diag = client.get("/saldos/diagnostico", headers=h).json()
    assert diag["sobregirado"] is True
    assert diag["saldo_actual"] == -200000.0
    assert any("sobregirado" in m.lower() for m in diag["motivos"])
    assert any("Mercado" in m for m in diag["motivos"])
    assert diag["top_categorias"][0]["monto"] == 300000.0
