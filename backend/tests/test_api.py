"""Tests de la API: auth, CRUD y aislamiento multi-usuario."""

import calendar
import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.defaults import DEFAULT_CATEGORIAS
from app.recurrencia import hoy as hoy_app

# Nº de categorías que recibe un usuario nuevo. Se lee de `app/defaults.py`
# para que añadir o quitar una categoría por defecto no deje el test en rojo.
N_DEFAULT = len(DEFAULT_CATEGORIAS)


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
    assert len(client.get("/categorias", headers=h).json()) == N_DEFAULT  # por defecto

    r = client.post("/categorias", headers=h, json={"nombre": "Mascotas", "tipo": "gasto"})
    assert r.status_code == 201
    cid = r.json()["id"]

    r = client.patch(f"/categorias/{cid}", headers=h, json={"color": "#000000"})
    assert r.json()["color"] == "#000000"

    assert client.delete(f"/categorias/{cid}", headers=h).status_code == 204
    assert len(client.get("/categorias", headers=h).json()) == N_DEFAULT


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
    # Al registrarse ya vienen las etiquetas del diccionario del OCR
    base = len(client.get("/etiquetas", headers=h).json())
    assert base > 0

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

    assert len(client.get("/etiquetas", headers=h).json()) == base + 2

    # transacción etiquetada con la subetiqueta
    tx = client.post(
        "/transacciones", headers=h,
        json={"tipo": "gasto", "monto": "5000", "fecha": "2026-09-27", "descripcion": "Almuerzo", "etiqueta_id": sub["id"]},
    ).json()
    assert tx["etiqueta_id"] == sub["id"]

    # borrar la raíz elimina la subetiqueta en cascada
    assert client.delete(f"/etiquetas/{root['id']}", headers=h).status_code == 204
    assert len(client.get("/etiquetas", headers=h).json()) == base


def test_alertas_de_pagos(client):
    _, h = _registrar(client)
    hoy = hoy_app()

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
    hoy = hoy_app()
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
    """Construye un PDF mínimo válido con un texto (para probar la extracción).

    Los paréntesis y la barra invertida se escapan: dentro de un literal de PDF
    (…) sin escapar, un `)` cierra la cadena y el PDF queda inválido.
    """
    seguro = texto.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
    contenido = f"BT /F1 24 Tf 72 720 Td ({seguro}) Tj ET".encode()
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
    # Regresión: `SUBTOTAL` no es el total, y el formato colombiano se lee bien.
    # Antes daba 22.616 (el subtotal, y encima como 22,6).
    assert detectar_monto(RECIBO) == Decimal("25116")
    assert detectar_monto("TOTAL A PAGAR $ 1.500.000,00") == Decimal("1500000.00")

    _, h = _registrar(client)
    pdf = _pdf_minimo("Factura Total: 250.00")
    r = client.post("/facturas", headers=h, files={"archivo": ("f.pdf", pdf, "application/pdf")})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["nombre_archivo"] == "f.pdf"
    assert f["monto_detectado"] is not None
    # El valor, no solo que exista: aquí es donde se colaba el error de escala
    assert Decimal(str(f["monto_detectado"])) == Decimal("250")
    assert len(client.get("/facturas", headers=h).json()) == 1


def test_presupuestos(client):
    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    mercado = next(c for c in cats if c["nombre"] == "Mercado")
    hoy = hoy_app()

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


def test_importar_csv_colombiano_no_corrompe_montos(client):
    """El formato colombiano (punto de miles) se importa entero y bien.

    Antes: `44.900` entraba como **44,9** y `1.500.000` **descartaba la fila** en
    silencio (dos puntos decimales no son un número válido).
    """
    _, h = _registrar(client)
    csv_txt = (
        "Fecha,Descripcion,Valor\n"
        "05/09/2026,NETFLIX.COM,44.900\n"
        "06/09/2026,ARRIENDO,1.500.000\n"
        "07/09/2026,NOMINA,4.500.000\n"
        "08/09/2026,4X1000 GMF,1.200\n"
    )
    r = client.post(
        "/importar/csv", headers=h,
        files={"archivo": ("banco.csv", csv_txt.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    assert datos["total"] == 4, "no se debe descartar ninguna fila"
    montos = [Decimal(str(f["monto"])) for f in datos["filas"]]
    assert montos == [
        Decimal("44900"), Decimal("1500000"), Decimal("4500000"), Decimal("1200")
    ]


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


def test_deuda_tarjeta_multimoneda(client):
    """Reproduce el extracto real: AMEX con deuda en COP y USD."""
    _, h = _registrar(client)
    tar = client.post("/tarjetas", headers=h, json={
        "nombre": "AMEX Platinum", "banco": "Bancolombia", "tipo": "credito",
        "moneda": "COP", "dia_corte": 20, "dia_pago": 5, "tasa_interes": "0.02",
    }).json()

    client.post(f"/tarjetas/{tar['id']}/deudas", headers=h, json={"moneda": "COP", "monto": "8912816", "notas": "extracto sep"})
    client.post(f"/tarjetas/{tar['id']}/deudas", headers=h, json={"moneda": "USD", "monto": "700"})

    t = client.get("/tarjetas", headers=h).json()[0]
    assert t["deuda_por_moneda"]["COP"] == 8912816.0
    assert t["deuda_por_moneda"]["USD"] == 700.0
    # sin tasa USD->COP no se puede dar el total
    assert t["deuda_total_cop"] is None

    # registro la TRM que aparecía en el extracto
    client.post("/tasas", headers=h, json={"moneda_origen": "USD", "moneda_destino": "COP", "tasa": "3329.61"})
    t = client.get("/tarjetas", headers=h).json()[0]
    esperado = 8912816 + 700 * 3329.61
    assert abs(t["deuda_total_cop"] - esperado) < 1

    # el simulador toma la deuda registrada sin volver a escribirla
    r = client.get(f"/tarjetas/{tar['id']}/simulador", headers=h)
    assert r.status_code == 200, r.text
    assert abs(float(r.json()["saldo_inicial"]) - esperado) < 1

    # se puede quitar una deuda
    deuda_id = t["deudas"][0]["id"]
    assert client.delete(f"/tarjetas/{tar['id']}/deudas/{deuda_id}", headers=h).status_code == 204
    assert len(client.get(f"/tarjetas/{tar['id']}/deudas", headers=h).json()) == 1


def test_tasa_ea_se_convierte_a_mensual(client):
    """El extracto da la tasa E.A.; la app la convierte a mensual para el simulador."""
    from app.intereses import mensual_desde_ea

    # 25,93 % E.A. -> 1,94 % mensual (dividir entre 12 daría 2,16 %)
    mensual = mensual_desde_ea(Decimal("0.2593"))
    assert abs(float(mensual) - 0.0194) < 0.0002

    _, h = _registrar(client)
    tar = client.post("/tarjetas", headers=h, json={
        "nombre": "AMEX Platinum", "banco": "Bancolombia", "tipo": "credito",
        "moneda": "COP", "tasa_interes_ea": "0.2593",
    }).json()
    assert abs(float(tar["tasa_interes"]) - 0.0194) < 0.0002
    assert float(tar["tasa_interes_ea"]) == 0.2593

    # el simulador usa la tasa mensual ya convertida
    r = client.get(f"/tarjetas/{tar['id']}/simulador", headers=h, params={"saldo": 1000000, "pago_mensual": 200000})
    assert r.status_code == 200, r.text
    assert abs(float(r.json()["tasa_mensual"]) - 0.0194) < 0.0002

    # si dan la mensual directa, también sirve
    tar2 = client.post("/tarjetas", headers=h, json={"nombre": "Otra", "tipo": "credito", "tasa_interes": "0.02"}).json()
    assert float(tar2["tasa_interes"]) == 0.02


def test_tasa_en_escala_equivocada_se_rechaza(client):
    """El error real: guardar 2,1593 (que es 215,93 %) en vez de 0,021593."""
    _, h = _registrar(client)

    r = client.post("/tarjetas", headers=h, json={"nombre": "Mala", "tipo": "credito", "tasa_interes": "2.1593"})
    assert r.status_code == 400, r.text
    assert "215" in r.json()["detail"]

    # la forma correcta (E.A. del extracto) pasa y convierte exacto
    r = client.post("/tarjetas", headers=h, json={"nombre": "AMEX", "tipo": "credito", "tasa_interes_ea": "0.292215"})
    assert r.status_code == 201, r.text
    tar = r.json()
    assert abs(float(tar["tasa_interes"]) - 0.021593) < 0.00001

    # y se puede corregir con PATCH (antes no había forma de editar)
    r = client.patch(f"/tarjetas/{tar['id']}", headers=h, json={"tasa_interes_ea": "0.292215", "tasa_interes": None})
    assert r.status_code == 200, r.text
    assert abs(float(r.json()["tasa_interes"]) - 0.021593) < 0.00001

    # E.A. absurda también se rechaza
    r = client.patch(f"/tarjetas/{tar['id']}", headers=h, json={"tasa_interes_ea": "29.2215"})
    assert r.status_code == 400


def test_editar_transaccion_y_asignar_etiquetas(client):
    """Editar un gasto ya registrado y ponerle etiqueta o subetiqueta."""
    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    vivienda = next(c for c in cats if c["nombre"] == "Vivienda")
    mercado = next(c for c in cats if c["nombre"] == "Mercado")

    etq = client.post("/etiquetas", headers=h, json={"nombre": "Hogar"}).json()
    sub = client.post("/etiquetas", headers=h, json={"nombre": "Internet", "padre_id": etq["id"]}).json()
    assert sub["padre_id"] == etq["id"]

    tx = client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "127240", "fecha": "2026-09-15",
        "descripcion": "Internet Movistar", "categoria_id": vivienda["id"],
    }).json()
    assert tx["etiqueta_id"] is None

    # edito monto, categoría, descripción y le asigno la SUBETIQUETA
    r = client.patch(f"/transacciones/{tx['id']}", headers=h, json={
        "monto": "130000",
        "categoria_id": mercado["id"],
        "etiqueta_id": sub["id"],
        "descripcion": "Internet Movistar (corregido)",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert float(d["monto"]) == 130000.0
    assert d["categoria_id"] == mercado["id"]
    assert d["etiqueta_id"] == sub["id"]
    assert d["descripcion"] == "Internet Movistar (corregido)"

    # sigue siendo un solo movimiento
    assert len(client.get("/transacciones", headers=h).json()) == 1

    # puedo quitar la etiqueta
    r = client.patch(f"/transacciones/{tx['id']}", headers=h, json={"etiqueta_id": None})
    assert r.status_code == 200
    assert r.json()["etiqueta_id"] is None


def test_tarjeta_debito_asociada_a_cuenta(client):
    """Débito = instrumento de una cuenta. Crédito = pasivo, no toca cuentas."""
    _, h = _registrar(client)

    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros Bancolombia", "tipo": "ahorro", "saldo_inicial": "3000000"}).json()

    # débito asociada a la cuenta de ahorros
    debito = client.post("/tarjetas", headers=h, json={
        "nombre": "Débito Ahorros", "banco": "Bancolombia", "tipo": "debito",
        "moneda": "COP", "cuenta_id": cuenta["id"],
    }).json()
    assert debito["cuenta_id"] == cuenta["id"]

    lista = client.get("/tarjetas", headers=h).json()
    d = next(t for t in lista if t["id"] == debito["id"])
    assert d["cuenta_nombre"] == "Ahorros Bancolombia"

    # el movimiento con la débito baja el saldo de ESA cuenta
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "127240", "fecha": hoy_app().isoformat(),
        "descripcion": "Internet Movistar", "tarjeta_id": debito["id"], "cuenta_id": cuenta["id"],
    })
    saldos = client.get("/saldos", headers=h).json()
    assert saldos["cuentas"][0]["saldo_actual"] == 2872760.0  # 3.000.000 − 127.240

    # el crédito NO se puede asociar a una cuenta (es un pasivo)
    credito = client.post("/tarjetas", headers=h, json={
        "nombre": "AMEX", "tipo": "credito", "cuenta_id": cuenta["id"],
    }).json()
    assert credito["cuenta_id"] is None

    # y si cambio una débito a crédito, se desasocia
    r = client.patch(f"/tarjetas/{debito['id']}", headers=h, json={"tipo": "credito"})
    assert r.status_code == 200
    assert r.json()["cuenta_id"] is None


def test_unicidad_entre_hermanos(client):
    """Categoría → Etiqueta → Subetiqueta. No se repiten hermanas (sin distinguir mayúsculas)."""
    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    vivienda = next(c for c in cats if c["nombre"] == "Vivienda")
    transporte = next(c for c in cats if c["nombre"] == "Transporte")

    # etiqueta dentro de una categoría
    r = client.post("/etiquetas", headers=h, json={"nombre": "Servicios", "categoria_id": vivienda["id"]})
    assert r.status_code == 201, r.text
    servicios = r.json()
    assert servicios["categoria_id"] == vivienda["id"]

    # NO se repite en la misma categoría (ni con otra capitalización)
    r = client.post("/etiquetas", headers=h, json={"nombre": "servicios", "categoria_id": vivienda["id"]})
    assert r.status_code == 400
    assert "Ya existe" in r.json()["detail"]

    # SÍ se repite en otra categoría
    r = client.post("/etiquetas", headers=h, json={"nombre": "Servicios", "categoria_id": transporte["id"]})
    assert r.status_code == 201

    # subetiqueta: hereda la categoría de su etiqueta
    r = client.post("/etiquetas", headers=h, json={"nombre": "Internet", "padre_id": servicios["id"]})
    assert r.status_code == 201
    sub = r.json()
    assert sub["categoria_id"] == vivienda["id"]

    # NO dos subetiquetas iguales bajo la misma etiqueta
    r = client.post("/etiquetas", headers=h, json={"nombre": "internet", "padre_id": servicios["id"]})
    assert r.status_code == 400

    # categorías: únicas entre hermanas
    assert client.post("/categorias", headers=h, json={"nombre": "Vivienda", "tipo": "gasto"}).status_code == 400
    assert client.post("/categorias", headers=h, json={"nombre": "vivienda", "tipo": "gasto"}).status_code == 400

    # las categorías son planas (sin subcategorías)
    assert client.get("/categorias/arbol", headers=h).json()[0]["subcategorias"] == []

    # la misma subetiqueta sí puede existir bajo etiquetas de categorías distintas
    serv_transporte = next(
        e for e in client.get("/etiquetas", headers=h).json()
        if e["nombre"].lower() == "servicios" and e["categoria_id"] == transporte["id"]
    )
    r = client.post("/etiquetas", headers=h, json={"nombre": "Internet", "padre_id": serv_transporte["id"]})
    assert r.status_code == 201


def test_siguiente_pago():
    from app.models import Periodicidad
    from app.recurrencia import siguiente_pago

    assert siguiente_pago(Periodicidad.SEMANAL, date(2026, 1, 1)) == date(2026, 1, 8)
    assert siguiente_pago(Periodicidad.MENSUAL, date(2026, 1, 15)) == date(2026, 2, 15)
    assert siguiente_pago(Periodicidad.MENSUAL, date(2026, 1, 31)) == date(2026, 2, 28)  # clamp
    assert siguiente_pago(Periodicidad.TRIMESTRAL, date(2026, 1, 15)) == date(2026, 4, 15)
    assert siguiente_pago(Periodicidad.ANUAL, date(2026, 3, 1)) == date(2027, 3, 1)


def test_suscripcion_genera_transaccion(client, engine):
    """Una suscripción vencida crea su gasto y avanza la fecha (idempotente)."""
    from sqlalchemy.orm import sessionmaker

    from app.recurrencia import procesar_suscripciones

    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    cat = next(c for c in cats if c["nombre"] == "Suscripciones")
    etq = client.post("/etiquetas", headers=h, json={"nombre": "Streaming", "categoria_id": cat["id"]}).json()
    sub_etq = client.post("/etiquetas", headers=h, json={"nombre": "Netflix", "padre_id": etq["id"]}).json()

    hoy = hoy_app()
    vencido = (hoy - timedelta(days=1)).isoformat()
    r = client.post("/suscripciones", headers=h, json={
        "nombre": "Netflix", "monto": "44900", "periodicidad": "mensual",
        "proximo_pago": vencido, "categoria_id": cat["id"], "etiqueta_id": sub_etq["id"],
    })
    assert r.status_code == 201, r.text

    sf = sessionmaker(bind=engine, expire_on_commit=False)
    with sf.begin() as s:
        assert procesar_suscripciones(s, hoy) == 1

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 1
    tx = txs[0]
    assert tx["tipo"] == "gasto"
    assert float(tx["monto"]) == 44900.0
    assert tx["descripcion"] == "Netflix"
    assert tx["categoria_id"] == cat["id"]
    assert tx["etiqueta_id"] == sub_etq["id"]  # cae en Suscripciones › Streaming › Netflix

    # idempotente: una segunda pasada no genera nada
    with sf.begin() as s:
        assert procesar_suscripciones(s, hoy) == 0
    assert len(client.get("/transacciones", headers=h).json()) == 1

    # y la próxima fecha avanzó
    assert client.get("/suscripciones", headers=h).json()[0]["proximo_pago"] != vencido


def test_suscripcion_pausada_no_genera(client, engine):
    from sqlalchemy.orm import sessionmaker

    from app.recurrencia import procesar_suscripciones

    _, h = _registrar(client)
    hoy = hoy_app()
    client.post("/suscripciones", headers=h, json={
        "nombre": "Pausada", "monto": "10000", "periodicidad": "mensual",
        "proximo_pago": (hoy - timedelta(days=5)).isoformat(), "estado": "pausada",
    })
    sf = sessionmaker(bind=engine, expire_on_commit=False)
    with sf.begin() as s:
        assert procesar_suscripciones(s, hoy) == 0
    assert client.get("/transacciones", headers=h).json() == []


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
    assert len(backup["categorias"]) == N_DEFAULT

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
    assert len(client.get("/categorias", headers=h).json()) == N_DEFAULT

    # exportar CSV
    r = client.get("/exportar/transacciones.csv", headers=h)
    assert r.status_code == 200
    assert "fecha,tipo,monto" in r.text


def test_flujo_caja(client):
    _, h = _registrar(client)
    hoy = hoy_app()

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
    futuro = (hoy_app() + timedelta(days=60)).isoformat()
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
        [{"fecha": hoy_app(), "dias_restantes": 0, "titulo": "Netflix", "monto": 50000, "moneda": "COP"}]
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

    # categoría (raíz) + etiqueta dentro de ella
    raiz = client.post("/categorias", headers=h, json={"nombre": "Movilidad", "tipo": "gasto"}).json()
    etq = client.post("/etiquetas", headers=h, json={"nombre": "Gasolina", "categoria_id": raiz["id"]}).json()
    assert etq["categoria_id"] == raiz["id"]

    arbol = client.get("/categorias/arbol", headers=h).json()
    assert any(n["nombre"] == "Movilidad" and n["subcategorias"] == [] for n in arbol)

    hoy = hoy_app()
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "200000", "fecha": hoy.isoformat(),
        "categoria_id": raiz["id"], "etiqueta_id": etq["id"], "cuenta_id": cta["id"],
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
    assert gasto["categoria"] == "Movilidad"
    assert gasto["etiqueta"] == "Gasolina"

    diag = client.get("/saldos/diagnostico", headers=h).json()
    assert diag["sobregirado"] is False
    assert diag["saldo_actual"] == 1300000.0
    assert diag["tiene_cuentas"] is True
    assert any("Movilidad" in m for m in diag["motivos"])

    cons = client.get("/saldos/consolidado?meses=3", headers=h).json()
    assert len(cons["meses"]) == 3
    assert cons["meses"][-1]["saldo_final"] == 1300000.0


def test_saldo_sin_cuentas_y_asignacion(client):
    """Sin cuentas el saldo es solo flujo; al crear una cuenta y adoptar movimientos, es real."""
    _, h = _registrar(client)
    hoy = hoy_app()
    comida = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado")

    # gasto sin cuenta
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "127240", "fecha": hoy.isoformat(), "categoria_id": comida["id"],
    })

    d = client.get("/saldos/diagnostico", headers=h).json()
    assert d["tiene_cuentas"] is False
    assert d["saldo_actual"] == -127240.0
    assert d["sin_cuenta_movimientos"] == 1
    assert any("No tienes cuentas" in m for m in d["motivos"])

    # creo la cuenta con el saldo real y adopto el movimiento huérfano
    cta = client.post("/cuentas", headers=h, json={"nombre": "Banco", "saldo_inicial": "5000000"}).json()
    r = client.post(f"/cuentas/{cta['id']}/adoptar-movimientos", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["asignados"] == 1
    assert r.json()["saldo_actual"] == 4872760.0  # 5.000.000 − 127.240

    d = client.get("/saldos/diagnostico", headers=h).json()
    assert d["tiene_cuentas"] is True
    assert d["saldo_actual"] == 4872760.0
    assert d["sin_cuenta_movimientos"] == 0


def test_diagnostico_de_sobregiro(client):
    _, h = _registrar(client)
    cta = client.post("/cuentas", headers=h, json={"nombre": "Efectivo", "saldo_inicial": "100000"}).json()
    hoy = hoy_app()
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


# --- OCR por línea --------------------------------------------------------- #

# Recibo colombiano con los dos formatos: descripción + línea de cantidad
# («PECHUGA POLLO BANDEJA» / «1.234 KG X 12.900  15.916») y todo en una línea.
RECIBO = """D1 SAS
NIT 900.123.456-7
FACTURA DE VENTA
PECHUGA POLLO BANDEJA
1.234 KG X 12.900            15.916
ARROZ DIANA 500G 2 UN X 2.500      5.000
LECHE ALQUERIA 1100ML               4.200
TOTAL                        25.116
EFECTIVO                     30.000
CAMBIO                        4.884
"""


def test_parser_de_lineas_de_recibo():
    """El parser entiende el formato de dinero colombiano y descarta lo que no es artículo."""
    from app.lineas import cantidad, detectar_tipo, monto, parsear_lineas

    # El punto separa miles y la coma es decimal
    assert str(monto("15.916")) == "15916"
    assert str(monto("15,50")) == "15.50"
    # La ambigüedad del peso se resuelve por unidad: 1.234 KG son 1,234 kg
    assert str(cantidad("1.234", "KG")) == "1.234"
    assert str(cantidad("1.234", "UN")) == "1234"

    articulos = parsear_lineas(RECIBO)
    assert [a["descripcion"] for a in articulos] == [
        "PECHUGA POLLO BANDEJA",
        "ARROZ DIANA 500G",
        "LECHE ALQUERIA 1100ML",
    ]
    assert articulos[0]["cantidad"] == Decimal("1.234")
    assert articulos[0]["valor_unitario"] == Decimal("12900")
    assert articulos[0]["valor_total"] == Decimal("15916")
    assert articulos[1]["valor_unitario"] == Decimal("2500")
    assert articulos[2]["valor_total"] == Decimal("4200")

    # Ni el total ni los medios de pago son artículos
    assert sum(a["valor_total"] for a in articulos) == Decimal("25116")
    assert detectar_tipo(RECIBO, articulos) == "mercado"


def test_ocr_por_linea_clasifica_aprende_y_confirma(client, engine):
    """Flujo completo: parsear → clasificar → corregir (aprende) → confirmar.

    Al registrarse se siembran las etiquetas del diccionario, así que la tira se
    clasifica **sola**. Para lo que el diccionario no conoce («SALSA BBQ») el
    usuario corrige una vez y a la siguiente se reconoce por historial.
    """
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]
    cat_mercado = next(
        c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado"
    )
    por_nombre = {e["nombre"]: e for e in client.get("/etiquetas", headers=h).json()}
    # Estas ya vienen de fábrica: son las que el diccionario sabe reconocer
    carnes, lacteos, despensa = por_nombre["Carnes"], por_nombre["Lácteos y huevos"], por_nombre["Despensa"]
    assert carnes["categoria_id"] == cat_mercado["id"]

    # Un artículo que el diccionario NO conoce, para probar el aprendizaje
    DESCONOCIDO = "PILAS AA DURACEL 4 UN"
    texto = RECIBO + f"{DESCONOCIDO}        7.300\n"

    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        factura = Factura(
            usuario_id=usuario_id,
            nombre_archivo="d1.txt",
            texto_extraido=texto,
            monto_detectado=Decimal("32416"),
            fecha_detectada=date(2026, 9, 20),
        )
        s.add(factura)
        s.flush()
        fid = str(factura.id)

    # 1) Parsear: las líneas quedan guardadas y clasificadas por diccionario
    r = client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    assert r.status_code == 200, r.text
    detalle = r.json()
    assert detalle["tipo_documento"] == "mercado"
    assert len(detalle["lineas"]) == 4

    por_desc = {li["descripcion"].split()[0]: li for li in detalle["lineas"]}
    assert por_desc["PECHUGA"]["origen"] == "diccionario"
    assert por_desc["PECHUGA"]["etiqueta_id"] == carnes["id"]
    assert por_desc["LECHE"]["etiqueta_id"] == lacteos["id"]
    assert por_desc["ARROZ"]["etiqueta_id"] == despensa["id"]
    # Lo desconocido queda sin clasificar, para que el usuario decida
    assert por_desc["PILAS"]["origen"] == "sin_clasificar"
    assert por_desc["PILAS"]["etiqueta_id"] is None

    # 2) Corregir las pilas: se aprende la regla
    pilas = client.post(
        "/etiquetas", headers=h, json={"nombre": "Pilas", "categoria_id": cat_mercado["id"]}
    ).json()
    r = client.patch(
        f"/facturas/{fid}/lineas/{por_desc['PILAS']['id']}",
        headers=h,
        json={"etiqueta_id": pilas["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["origen"] == "manual"
    assert r.json()["confianza"] == "1.000"

    # 3) Re-parsear: ahora las pilas se reconocen por historial (y no se duplican)
    r = client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    assert len(r.json()["lineas"]) == 4
    pilas_leidas = next(li for li in r.json()["lineas"] if li["descripcion"].startswith("PILAS"))
    assert pilas_leidas["origen"] == "historial"
    assert pilas_leidas["etiqueta_id"] == pilas["id"]

    # 4) Confirmar: una transacción de gasto por línea, con su categoría y etiqueta
    r = client.post(f"/facturas/{fid}/confirmar", headers=h, json={})
    assert r.status_code == 200, r.text
    assert all(li["transaccion_id"] for li in r.json()["lineas"])

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 4
    assert all(t["tipo"] == "gasto" for t in txs)
    assert sum(Decimal(t["monto"]) for t in txs) == Decimal("32416")
    assert all(t["categoria_id"] == cat_mercado["id"] for t in txs)
    assert all(t["fecha"] == "2026-09-20" for t in txs)
    assert {t["etiqueta_id"] for t in txs} == {
        carnes["id"], lacteos["id"], despensa["id"], pilas["id"],
    }

    # 5) Idempotente: ya no quedan líneas pendientes
    assert client.post(f"/facturas/{fid}/confirmar", headers=h, json={}).status_code == 400

    # 6) Una línea ya confirmada no se puede editar ni borrar
    linea_id = r.json()["lineas"][0]["id"]
    assert client.patch(
        f"/facturas/{fid}/lineas/{linea_id}", headers=h, json={"valor_total": "1"}
    ).status_code == 409
    assert client.delete(f"/facturas/{fid}/lineas/{linea_id}", headers=h).status_code == 409


def test_ocr_linea_descartar_y_aislamiento(client, engine):
    """Se pueden descartar líneas y no se ven facturas de otro usuario."""
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]
    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        factura = Factura(usuario_id=usuario_id, nombre_archivo="r.txt", texto_extraido=RECIBO)
        s.add(factura)
        s.flush()
        fid = str(factura.id)

    detalle = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()
    primera = detalle["lineas"][0]["id"]
    assert client.delete(f"/facturas/{fid}/lineas/{primera}", headers=h).status_code == 204
    assert len(client.get(f"/facturas/{fid}", headers=h).json()["lineas"]) == 2

    # Otro usuario no ve ni toca esta factura
    _, h2 = _registrar(client)
    assert client.get(f"/facturas/{fid}", headers=h2).status_code == 404
    assert client.post(f"/facturas/{fid}/lineas", headers=h2, json={}).status_code == 404
    assert len(client.get(f"/facturas/{fid}", headers=h).json()["lineas"]) == 2


def test_notificaciones_whatsapp(client):
    """WhatsApp como canal: mapeo, destino persistido y fallo claro sin credenciales."""
    from app.models import ConfigNotificaciones
    from app.notificaciones import canales_de, enviar

    # `ambos` sigue siendo telegram+correo; `todos` añade WhatsApp
    assert canales_de(ConfigNotificaciones(canal="todos")) == ["telegram", "email", "whatsapp"]
    assert canales_de(ConfigNotificaciones(canal="ambos")) == ["telegram", "email"]
    assert canales_de(ConfigNotificaciones(canal="whatsapp")) == ["whatsapp"]

    # Sin las credenciales del servidor el canal avisa, no revienta
    try:
        enviar(
            ConfigNotificaciones(canal="whatsapp", whatsapp_numero="573001234567"),
            [],
        )
        raise AssertionError("debía fallar sin FINANZAS_WHATSAPP_TOKEN")
    except RuntimeError as exc:
        assert "FINANZAS_WHATSAPP_TOKEN" in str(exc)

    _, h = _registrar(client)
    r = client.put(
        "/notificaciones",
        headers=h,
        json={
            "canal": "whatsapp",
            "whatsapp_numero": "573001234567",
            "dias_anticipacion": 3,
            "activo": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["canal"] == "whatsapp"
    assert r.json()["whatsapp_numero"] == "573001234567"
    assert client.get("/notificaciones", headers=h).json()["whatsapp_numero"] == "573001234567"

    # Probar sin credenciales: 502 con un mensaje que dice qué falta
    r = client.post("/notificaciones/probar", headers=h)
    assert r.status_code == 502
    assert "WHATSAPP" in r.json()["detail"]

    # Un canal que no existe se rechaza en la validación
    assert client.put("/notificaciones", headers=h, json={"canal": "paloma"}).status_code == 422



# --- pólizas de seguro (personas y vehículos) ------------------------------ #


def test_polizas_crud_y_aislamiento(client):
    """Póliza de vehículo: datos del bien, vigencia, edición y aislamiento."""
    _, h = _registrar(client)
    hoy = hoy_app()

    r = client.post(
        "/polizas",
        headers=h,
        json={
            "tipo": "vehiculo",
            "aseguradora": "Sura",
            "numero_poliza": "POL-123",
            "placa": "ABC123",
            "marca": "Renault",
            "modelo": "Sandero",
            "anio": 2019,
            "valor_asegurado": "45000000",
            "prima": "1200000",
            "periodicidad": "semestral",
            "fecha_inicio": hoy.isoformat(),
            "fecha_fin": (hoy + timedelta(days=365)).isoformat(),
            "proximo_pago": (hoy + timedelta(days=10)).isoformat(),
        },
    )
    assert r.status_code == 201, r.text
    pol = r.json()
    assert pol["titulo"] == "Vehículo ABC123 (Sura)"
    assert pol["placa"] == "ABC123"
    assert pol["valor_asegurado"] == "45000000.00"
    # semestral: la prima pesa 1/6 al mes
    assert pol["prima_mensual_cop"] == 200000.0

    assert len(client.get("/polizas", headers=h).json()) == 1

    # Editar: pausar y corregir la placa
    r = client.patch(f"/polizas/{pol['id']}", headers=h, json={"estado": "pausada", "placa": "XYZ789"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "pausada"
    assert r.json()["titulo"] == "Vehículo XYZ789 (Sura)"

    # Validaciones
    assert client.post("/polizas", headers=h, json={"aseguradora": "X", "prima": "0"}).status_code == 422
    assert client.post(
        "/polizas",
        headers=h,
        json={
            "aseguradora": "X", "prima": "100", "fecha_inicio": hoy.isoformat(),
            "fecha_fin": (hoy - timedelta(days=1)).isoformat(),
        },
    ).status_code == 422

    # Otro usuario no la ve ni la toca
    _, h2 = _registrar(client)
    assert client.get(f"/polizas/{pol['id']}", headers=h2).status_code == 404
    assert client.patch(f"/polizas/{pol['id']}", headers=h2, json={"prima": "1"}).status_code == 404
    assert client.delete(f"/polizas/{pol['id']}", headers=h2).status_code == 404
    assert client.get("/polizas", headers=h2).json() == []

    assert client.delete(f"/polizas/{pol['id']}", headers=h).status_code == 204
    assert client.get("/polizas", headers=h).json() == []


def test_poliza_beneficiarios_no_pasan_de_100(client):
    """Los porcentajes de los beneficiarios no pueden sumar más de 100 (seguro de vida)."""
    _, h = _registrar(client)
    pol = client.post(
        "/polizas",
        headers=h,
        json={"tipo": "vida", "aseguradora": "Bolívar", "asegurado_nombre": "Ana", "prima": "90000"},
    ).json()
    assert pol["titulo"] == "Ana (Bolívar)"

    primera = client.post(
        f"/polizas/{pol['id']}/beneficiarios", headers=h,
        json={"nombre": "Luis", "parentesco": "hijo", "porcentaje": "60"},
    )
    assert primera.status_code == 201, primera.text

    # 60 + 50 = 110 -> se rechaza con un mensaje que dice cuánto suma
    r = client.post(
        f"/polizas/{pol['id']}/beneficiarios", headers=h,
        json={"nombre": "Marta", "parentesco": "cónyuge", "porcentaje": "50"},
    )
    assert r.status_code == 400
    assert "110" in r.json()["detail"]

    segunda = client.post(
        f"/polizas/{pol['id']}/beneficiarios", headers=h,
        json={"nombre": "Marta", "parentesco": "cónyuge", "porcentaje": "40"},
    )
    assert segunda.status_code == 201

    # Editar el primero a 70 sumaría 110 -> rechazado; a 60 sigue válido
    b1 = primera.json()["id"]
    assert client.patch(
        f"/polizas/beneficiarios/{b1}", headers=h,
        json={"nombre": "Luis", "porcentaje": "70"},
    ).status_code == 400
    assert client.patch(
        f"/polizas/beneficiarios/{b1}", headers=h,
        json={"nombre": "Luis", "porcentaje": "60"},
    ).status_code == 200

    # La póliza trae sus beneficiarios
    detalle = client.get(f"/polizas/{pol['id']}", headers=h).json()
    assert [b["nombre"] for b in detalle["beneficiarios"]] == ["Luis", "Marta"]

    # Al borrar la póliza se van sus beneficiarios
    assert client.delete(f"/polizas/{pol['id']}", headers=h).status_code == 204
    assert client.patch(
        f"/polizas/beneficiarios/{b1}", headers=h, json={"nombre": "Luis"}
    ).status_code == 404


def test_poliza_genera_su_gasto(client, engine):
    """La prima vencida genera el gasto (idempotente) y se pone al día."""
    from sqlalchemy.orm import sessionmaker

    from app.models import Poliza
    from app.recurrencia import procesar_polizas

    _, h = _registrar(client)
    cats = client.get("/categorias", headers=h).json()
    cat = next(c for c in cats if c["nombre"] == "Vivienda")
    cta = client.post("/cuentas", headers=h, json={"nombre": "Efectivo", "saldo_inicial": "0"}).json()
    hoy_ = hoy_app()

    pol = client.post(
        "/polizas",
        headers=h,
        json={
            "tipo": "hogar", "aseguradora": "Sura", "prima": "180000", "periodicidad": "mensual",
            "proximo_pago": (hoy_ - timedelta(days=1)).isoformat(),
            "categoria_id": cat["id"], "cuenta_id": cta["id"],
        },
    ).json()

    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        assert procesar_polizas(s, hoy_) == 1
    with Session.begin() as s:
        assert procesar_polizas(s, hoy_) == 0  # idempotente: ya avanzó el periodo

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 1
    assert txs[0]["tipo"] == "gasto"
    assert txs[0]["monto"] == "180000.00"
    assert txs[0]["descripcion"] == "Seguro Hogar (Sura)"
    assert txs[0]["categoria_id"] == cat["id"]
    assert txs[0]["cuenta_id"] == cta["id"]
    assert txs[0]["poliza_id"] == pol["id"]

    # Se pone al día: tres periodos vencidos -> tres gastos
    with Session.begin() as s:
        p = s.get(Poliza, __import__("uuid").UUID(pol["id"]))
        p.proximo_pago = hoy_ - timedelta(days=80)
    with Session.begin() as s:
        assert procesar_polizas(s, hoy_) == 3
    assert len(client.get("/transacciones", headers=h).json()) == 4

    # Una póliza pausada no genera nada
    client.patch(f"/polizas/{pol['id']}", headers=h, json={"estado": "pausada"})
    with Session.begin() as s:
        p = s.get(Poliza, __import__("uuid").UUID(pol["id"]))
        p.proximo_pago = hoy_ - timedelta(days=1)
        s.flush()
        assert procesar_polizas(s, hoy_) == 0


def test_polizas_alertas_y_resumen(client):
    """Alertas de prima y de vencimiento de vigencia, y costo normalizado a COP."""
    _, h = _registrar(client)
    hoy_ = hoy_app()

    client.post("/polizas", headers=h, json={
        "tipo": "salud", "aseguradora": "Colsanitas", "asegurado_nombre": "Ana",
        "prima": "600000", "periodicidad": "anual",
        "proximo_pago": (hoy_ + timedelta(days=5)).isoformat(),
        "fecha_fin": (hoy_ + timedelta(days=10)).isoformat(),
    })
    client.post("/polizas", headers=h, json={
        "tipo": "vehiculo", "aseguradora": "Sura", "placa": "ABC123",
        "prima": "100", "moneda": "USD", "periodicidad": "mensual",
        "proximo_pago": (hoy_ + timedelta(days=3)).isoformat(),
        "fecha_fin": (hoy_ + timedelta(days=10)).isoformat(),
        "renovacion_automatica": True,
    })

    tipos = [a["tipo"] for a in client.get("/alertas", headers=h, params={"dias": 15}).json()]
    assert tipos.count("poliza_pago") == 2
    # La de salud avisa del vencimiento; la del vehículo renueva sola, así que no
    assert tipos.count("poliza_vencimiento") == 1

    resumen = client.get("/polizas/resumen", headers=h).json()
    assert resumen["polizas_activas"] == 2
    # 600000 anual = 50000/mes; la de USD no se puede sumar sin tasa
    assert resumen["prima_mensual_cop"] == 50000.0
    assert resumen["prima_anual_cop"] == 600000.0
    assert resumen["sin_tasa"] == ["USD"]

    # Con la tasa registrada ya se puede sumar
    client.post("/tasas", headers=h, json={"moneda_origen": "USD", "moneda_destino": "COP", "tasa": "4000"})
    resumen = client.get("/polizas/resumen", headers=h).json()
    assert resumen["prima_mensual_cop"] == 450000.0  # 50000 + 100*4000
    assert resumen["sin_tasa"] == []

    # Y entra en el gasto fijo del diagnóstico
    diag = client.get("/saldos/diagnostico", headers=h).json()
    assert diag["gastos_fijos"] == 450000.0


def test_respaldo_incluye_polizas_y_lo_que_faltaba(client):
    """El respaldo no debe perder pólizas, cuentas, metas, deudas ni líneas de factura."""
    _, h = _registrar(client)
    cat = client.get("/categorias", headers=h).json()[0]
    cta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "500000"}).json()
    meta = client.post("/metas", headers=h, json={"nombre": "Viaje", "monto_objetivo": "3000000"}).json()
    client.post(f"/metas/{meta['id']}/aportes", headers=h, json={"monto": "100000"})
    tarjeta = client.post("/tarjetas", headers=h, json={"nombre": "Visa", "tipo": "credito", "banco": "Bogotá"}).json()
    client.post(f"/tarjetas/{tarjeta['id']}/deudas", headers=h, json={"monto": "250000", "moneda": "COP"})
    pol = client.post("/polizas", headers=h, json={
        "tipo": "vida", "aseguradora": "Bolívar", "asegurado_nombre": "Ana", "prima": "90000",
        "categoria_id": cat["id"], "cuenta_id": cta["id"],
    }).json()
    client.post(f"/polizas/{pol['id']}/beneficiarios", headers=h, json={"nombre": "Luis", "porcentaje": "100"})
    client.post(f"/polizas/{pol['id']}/asegurados", headers=h, json={
        "nombre": "Ana", "parentesco": "titular", "es_titular": True,
    })

    backup = client.get("/exportar/json", headers=h).json()
    for clave in ("polizas", "beneficiarios", "poliza_asegurados", "cuentas", "metas_ahorro", "aportes_meta", "deudas_tarjeta"):
        assert backup[clave], f"el respaldo no incluye {clave}"
    assert backup["polizas"][0]["placa"] is None
    assert backup["beneficiarios"][0]["nombre"] == "Luis"
    assert backup["poliza_asegurados"][0]["nombre"] == "Ana"

    # Se borra todo y se restaura. Ojo: `GET /cuentas` devuelve el resumen con
    # totales, no una lista (el listado va en la clave `cuentas`).
    for ruta in ("/polizas", "/metas", "/tarjetas"):
        for item in client.get(ruta, headers=h).json():
            client.delete(f"{ruta}/{item['id']}", headers=h)
    for item in client.get("/cuentas", headers=h).json()["cuentas"]:
        client.delete(f"/cuentas/{item['id']}", headers=h)
    assert client.get("/cuentas", headers=h).json()["cuentas"] == []
    assert client.get("/polizas", headers=h).json() == []

    import json as _json

    r = client.post(
        "/respaldar/restaurar", headers=h,
        files={"archivo": ("respaldo.json", _json.dumps(backup).encode(), "application/json")},
    )
    assert r.status_code == 200, r.text

    polizas = client.get("/polizas", headers=h).json()
    assert len(polizas) == 1
    assert polizas[0]["beneficiarios"][0]["nombre"] == "Luis"
    assert len(client.get("/cuentas", headers=h).json()["cuentas"]) == 1
    assert len(client.get("/metas", headers=h).json()) == 1
    assert len(client.get("/tarjetas", headers=h).json()) == 1
    # El saldo de la cuenta sobrevive al respaldo
    assert client.get("/saldos", headers=h).json()["saldo_inicial_total"] == 500000.0


# --- flujo de caja: monedas, pólizas y doble conteo ------------------------ #


def test_flujo_caja_convierte_monedas_y_suma_polizas(client):
    """El flujo de caja no puede mezclar monedas ni ignorar las pólizas."""
    _, h = _registrar(client)
    hoy_ = hoy_app()
    client.post("/tasas", headers=h, json={"moneda_origen": "USD", "moneda_destino": "COP", "tasa": "4000"})

    # Suscripción de USD 10 al mes -> 40.000 COP, no 10
    client.post("/suscripciones", headers=h, json={
        "nombre": "Spotify", "monto": "10", "moneda": "USD",
        "periodicidad": "mensual", "proximo_pago": hoy_.isoformat(),
    })
    # Póliza semestral de 600.000: dos primas en 12 meses, no doce
    client.post("/polizas", headers=h, json={
        "tipo": "vehiculo", "aseguradora": "Sura", "placa": "ABC123",
        "prima": "600000", "periodicidad": "semestral", "proximo_pago": hoy_.isoformat(),
    })

    d = client.get("/flujo-caja?meses=12", headers=h).json()
    assert len(d["meses"]) == 12
    # El mes en curso paga la prima semestral y la suscripción convertida
    assert d["meses"][0]["gastos_fijos"] == 640000.0
    # 12 meses de suscripción (40.000) + 2 primas semestrales (600.000)
    total_fijos = sum(m["gastos_fijos"] for m in d["meses"])
    assert abs(total_fijos - (12 * 40000 + 2 * 600000)) < 0.01
    # Un mes sin prima solo tiene la suscripción
    assert d["meses"][1]["gastos_fijos"] == 40000.0
    assert d["sin_tasa"] == []


def test_flujo_caja_avisa_de_monedas_sin_tasa(client):
    """Sin tasa de cambio no se suma: se avisa, en vez de inventar el número."""
    _, h = _registrar(client)
    hoy_ = hoy_app()
    client.post("/suscripciones", headers=h, json={
        "nombre": "Revista", "monto": "5", "moneda": "EUR",
        "periodicidad": "mensual", "proximo_pago": hoy_.isoformat(),
    })
    client.post("/suscripciones", headers=h, json={
        "nombre": "Local", "monto": "20000", "periodicidad": "mensual",
        "proximo_pago": hoy_.isoformat(),
    })

    d = client.get("/flujo-caja?meses=6", headers=h).json()
    assert d["sin_tasa"] == ["EUR"]
    assert d["meses"][0]["gastos_fijos"] == 20000.0  # solo la que está en COP


def test_flujo_caja_no_cuenta_dos_veces_el_gasto_de_una_poliza(client, engine):
    """El gasto que genera una póliza es fijo, no variable: no puede contarse dos veces."""
    from sqlalchemy.orm import sessionmaker

    from app.recurrencia import procesar_polizas

    _, h = _registrar(client)
    hoy_ = hoy_app()
    # El 10 del mes anterior: cae dentro de los meses completos del promedio
    mes_anterior = (date(hoy_.year, hoy_.month, 1) - timedelta(days=1)).replace(day=10)
    pol = client.post("/polizas", headers=h, json={
        "tipo": "hogar", "aseguradora": "Sura", "prima": "180000",
        "periodicidad": "mensual", "proximo_pago": mes_anterior.isoformat(),
    }).json()

    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        # La puesta al día genera 1 o 2 periodos según el día del mes
        assert procesar_polizas(s, hoy_) >= 1

    txs = client.get("/transacciones", headers=h).json()
    assert txs and all(t["poliza_id"] == pol["id"] for t in txs)

    d = client.get("/flujo-caja?meses=6", headers=h).json()
    # El único gasto es el de la póliza: el promedio variable debe ser cero
    assert d["gasto_variable_promedio"] == 0.0


def test_reportes_seguros_por_tipo(client):
    """El reporte de seguros: costo anual, desglose por tipo y monedas sin tasa."""
    _, h = _registrar(client)
    hoy_ = hoy_app()

    # 600.000 al año -> 50.000/mes
    client.post("/polizas", headers=h, json={
        "tipo": "vida", "aseguradora": "Bolívar", "asegurado_nombre": "Ana",
        "prima": "600000", "periodicidad": "anual",
        "proximo_pago": hoy_.isoformat(),
    })
    # 300.000 cada 6 meses -> 50.000/mes
    client.post("/polizas", headers=h, json={
        "tipo": "vehiculo", "aseguradora": "Sura", "placa": "ABC123",
        "prima": "300000", "periodicidad": "semestral",
        "proximo_pago": hoy_.isoformat(),
    })
    # En otra moneda y sin tasa: no se suma, se informa
    client.post("/polizas", headers=h, json={
        "tipo": "salud", "aseguradora": "Colsanitas", "prima": "100",
        "moneda": "USD", "periodicidad": "mensual",
        "proximo_pago": hoy_.isoformat(),
    })
    # Pausada: fuera del reporte
    pausada = client.post("/polizas", headers=h, json={
        "tipo": "hogar", "aseguradora": "Sura", "prima": "500000",
        "periodicidad": "mensual", "proximo_pago": hoy_.isoformat(),
    }).json()
    client.patch(f"/polizas/{pausada['id']}", headers=h, json={"estado": "pausada"})

    r = client.get("/reportes/seguros", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["polizas_activas"] == 3  # las activas, tenga o no tasa
    assert d["prima_mensual_cop"] == 100000.0
    assert d["prima_anual_cop"] == 1200000.0
    assert d["sin_tasa"] == ["USD"]
    assert {t["tipo"]: t["prima_mensual_cop"] for t in d["por_tipo"]} == {
        "vida": 50000.0,
        "vehiculo": 50000.0,
    }

    # `/polizas/resumen` comparte la lógica: mismo resultado
    assert client.get("/polizas/resumen", headers=h).json() == d

    # Otro usuario no ve nada
    _, h2 = _registrar(client)
    assert client.get("/reportes/seguros", headers=h2).json()["prima_mensual_cop"] == 0.0


def test_poliza_con_varias_personas_aseguradas(client):
    """Una póliza familiar cubre a varias personas, con un solo titular."""
    _, h = _registrar(client)
    pol = client.post("/polizas", headers=h, json={
        "tipo": "vida", "aseguradora": "Bolívar", "asegurado_nombre": "Ana",
        "prima": "90000",
    }).json()
    pid = pol["id"]

    ana = client.post(f"/polizas/{pid}/asegurados", headers=h, json={
        "nombre": "Ana", "parentesco": "titular", "es_titular": True,
        "fecha_nacimiento": "1985-04-12",
    })
    assert ana.status_code == 201, ana.text
    assert ana.json()["es_titular"] is True

    luis = client.post(f"/polizas/{pid}/asegurados", headers=h, json={
        "nombre": "Luis", "parentesco": "hijo", "fecha_nacimiento": "2015-09-01",
    }).json()
    marta = client.post(f"/polizas/{pid}/asegurados", headers=h, json={
        "nombre": "Marta", "parentesco": "cónyuge",
    }).json()

    detalle = client.get(f"/polizas/{pid}", headers=h).json()
    assert [a["nombre"] for a in detalle["asegurados"]] == ["Ana", "Luis", "Marta"]

    # Al marcar otro titular, el anterior deja de serlo (solo uno por póliza)
    assert client.patch(f"/polizas/asegurados/{marta['id']}", headers=h, json={
        "nombre": "Marta", "parentesco": "cónyuge", "es_titular": True,
    }).status_code == 200
    titulares = [a["nombre"] for a in client.get(f"/polizas/{pid}", headers=h).json()["asegurados"] if a["es_titular"]]
    assert titulares == ["Marta"]

    # El asegurado principal de la póliza se conserva (compatibilidad)
    assert detalle["asegurado_nombre"] == "Ana"

    # Una fecha de nacimiento futura se rechaza
    assert client.post(f"/polizas/{pid}/asegurados", headers=h, json={
        "nombre": "Bebé", "fecha_nacimiento": "2099-01-01",
    }).status_code == 422

    # Aislamiento y borrado
    _, h2 = _registrar(client)
    assert client.patch(f"/polizas/asegurados/{luis['id']}", headers=h2, json={"nombre": "X"}).status_code == 404
    assert client.delete(f"/polizas/asegurados/{luis['id']}", headers=h2).status_code == 404
    assert client.delete(f"/polizas/asegurados/{luis['id']}", headers=h).status_code == 204

    # Al borrar la póliza se van sus asegurados
    assert client.delete(f"/polizas/{pid}", headers=h).status_code == 204
    assert client.delete(f"/polizas/asegurados/{marta['id']}", headers=h).status_code == 404


# --- OCR: de dónde sale el dinero, etiquetas de fábrica y compras que no son mercado --- #

ROPA = """TIENDA DE ROPA SAS
JEANS LEVIS 501 TALLA 32           189.900
CAMISETA ALGODON NEGRA              59.900
ZAPATILLAS ADIDAS TALLA 42         249.900
TOTAL                              499.700
"""


def test_ocr_confirma_con_tarjeta_y_fecha(client, engine):
    """Al confirmar hay que decir de dónde sale el dinero (tarjeta) y cuándo."""
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]

    credito = client.post("/tarjetas", headers=h, json={
        "nombre": "Visa", "tipo": "credito", "banco": "Bogotá",
    }).json()
    cuenta = client.post("/cuentas", headers=h, json={
        "nombre": "Ahorros", "saldo_inicial": "0",
    }).json()
    debito = client.post("/tarjetas", headers=h, json={
        "nombre": "Débito Bogotá", "tipo": "debito", "cuenta_id": cuenta["id"],
    }).json()

    Session = sessionmaker(bind=engine)

    def nueva_factura(nombre):
        with Session.begin() as s:
            f = Factura(usuario_id=usuario_id, nombre_archivo=nombre, texto_extraido=ROPA)
            s.add(f)
            s.flush()
            return str(f.id)

    # 1) Con tarjeta de crédito y una fecha distinta a la de hoy
    fid = nueva_factura("credito.txt")
    client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    r = client.post(f"/facturas/{fid}/confirmar", headers=h, json={
        "tarjeta_id": credito["id"], "fecha": "2026-08-30",
    })
    assert r.status_code == 200, r.text
    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 3
    assert all(t["tarjeta_id"] == credito["id"] for t in txs)
    assert all(t["fecha"] == "2026-08-30" for t in txs), "la fecha indicada manda sobre la detectada"
    assert all(t["cuenta_id"] is None for t in txs)

    # 2) Con tarjeta de débito: hereda la cuenta de la tarjeta (es su instrumento)
    fid = nueva_factura("debito.txt")
    client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    r = client.post(f"/facturas/{fid}/confirmar", headers=h, json={"tarjeta_id": debito["id"]})
    assert r.status_code == 200, r.text
    nuevas = [t for t in client.get("/transacciones", headers=h).json() if t["tarjeta_id"] == debito["id"]]
    assert len(nuevas) == 3
    assert all(t["cuenta_id"] == cuenta["id"] for t in nuevas)

    # 3) Aislamiento: otro usuario no puede usar mi tarjeta en su propia factura
    _, h2 = _registrar(client)
    usuario2 = client.get("/auth/me", headers=h2).json()["id"]
    with Session.begin() as s:
        ajena = Factura(usuario_id=usuario2, nombre_archivo="suya.txt", texto_extraido=ROPA)
        s.add(ajena)
        s.flush()
        fid_ajena = str(ajena.id)
    assert client.post(f"/facturas/{fid_ajena}/lineas", headers=h2, json={}).status_code == 200
    r = client.post(f"/facturas/{fid_ajena}/confirmar", headers=h2, json={"tarjeta_id": credito["id"]})
    assert r.status_code == 404, "una tarjeta de otro usuario no se puede usar"
    # Y mi factura sigue siendo invisible para él
    assert client.get(f"/facturas/{fid_ajena}", headers=h).status_code == 404


def test_compra_de_ropa_se_clasifica_sola(client, engine):
    """Un recibo que no es de mercado (ropa, calzado) también se clasifica solo."""
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]
    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        f = Factura(usuario_id=usuario_id, nombre_archivo="ropa.txt", texto_extraido=ROPA)
        s.add(f)
        s.flush()
        fid = str(f.id)

    detalle = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()
    por_desc = {li["descripcion"].split()[0]: li for li in detalle["lineas"]}
    assert por_desc["JEANS"]["origen"] == "diccionario"
    assert por_desc["CAMISETA"]["origen"] == "diccionario"
    assert por_desc["ZAPATILLAS"]["origen"] == "diccionario"

    etiquetas = {e["id"]: e["nombre"] for e in client.get("/etiquetas", headers=h).json()}
    assert etiquetas[por_desc["JEANS"]["etiqueta_id"]] == "Ropa"
    assert etiquetas[por_desc["CAMISETA"]["etiqueta_id"]] == "Ropa"
    assert etiquetas[por_desc["ZAPATILLAS"]["etiqueta_id"]] == "Calzado"

    # Y quedan en una categoría real (no sin categoría) al confirmar
    client.post(f"/facturas/{fid}/confirmar", headers=h, json={})
    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 3
    assert all(t["categoria_id"] is not None for t in txs), "un gasto sin categoría no sale en reportes"
    assert all(t["etiqueta_id"] is not None for t in txs)


def test_etiquetas_diccionario_endpoint(client):
    """Las etiquetas del diccionario se pueden sembrar en una cuenta ya existente."""
    _, h = _registrar(client)
    todas = client.get("/etiquetas", headers=h).json()
    # Un usuario nuevo ya las tiene: el endpoint no duplica nada
    r = client.post("/etiquetas/diccionario", headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["total_creadas"] == 0
    assert len(client.get("/etiquetas", headers=h).json()) == len(todas)

    # Si el usuario las borra, el endpoint las vuelve a crear
    for e in todas:
        client.delete(f"/etiquetas/{e['id']}", headers=h)
    assert client.get("/etiquetas", headers=h).json() == []

    r = client.post("/etiquetas/diccionario", headers=h)
    creadas = r.json()["creadas"]
    assert r.json()["total_creadas"] == len(creadas) > 0
    nombres = {e["nombre"] for e in creadas}
    assert {"Carnes", "Despensa", "Gasolina", "Ropa"} <= nombres

    # Idempotente
    assert client.post("/etiquetas/diccionario", headers=h).json()["total_creadas"] == 0

    # Si el usuario borró la categoría de destino, se salta esas etiquetas sin fallar
    mercado = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado")
    client.delete(f"/categorias/{mercado['id']}", headers=h)
    for e in client.get("/etiquetas", headers=h).json():
        if e["categoria_id"] is None:
            client.delete(f"/etiquetas/{e['id']}", headers=h)
    r = client.post("/etiquetas/diccionario", headers=h)
    assert r.status_code == 201
    assert "Carnes" not in {e["nombre"] for e in r.json()["creadas"]}


def test_diccionario_y_etiquetas_por_defecto_no_se_desincronizan():
    """Guardia: cada etiqueta por defecto tiene que estar en el diccionario del OCR.

    Si alguien añade una etiqueta a `ETIQUETAS_DICCIONARIO` que el clasificador no
    conoce, se siembra para nada y el OCR nunca la usará.
    """
    from app.clasificador import DICCIONARIO
    from app.defaults import ETIQUETAS_DICCIONARIO

    por_defecto = {n for nombres in ETIQUETAS_DICCIONARIO.values() for n in nombres}
    desconocidas = sorted(por_defecto - set(DICCIONARIO))
    assert not desconocidas, f"etiquetas sembradas que el diccionario no reconoce: {desconocidas}"

    # Y al revés: lo que el diccionario sabe reconocer debería poder sembrarse
    sin_sembrar = sorted(set(DICCIONARIO) - por_defecto)
    assert not sin_sembrar, f"el diccionario reconoce etiquetas que no se siembran: {sin_sembrar}"


def test_ocr_asigna_etiqueta_en_bloque(client, engine):
    """Una tira larga: asignar una etiqueta a las líneas sin clasificar de una vez."""
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]
    cat_mercado = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado")
    por_nombre = {e["nombre"]: e for e in client.get("/etiquetas", headers=h).json()}

    # Dos artículos que el diccionario NO conoce, mezclados con uno que sí
    TEXTO = RECIBO + "PILAS AA DURACEL 4 UN        7.300\nVELA AROMATICA VAINILLA      9.900\n"
    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        f = Factura(usuario_id=usuario_id, nombre_archivo="tira.txt", texto_extraido=TEXTO)
        s.add(f)
        s.flush()
        fid = str(f.id)

    detalle = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()
    por_desc = {li["descripcion"].split()[0]: li for li in detalle["lineas"]}
    assert por_desc["PECHUGA"]["origen"] == "diccionario"
    sin_clasificar = [li for li in detalle["lineas"] if li["origen"] == "sin_clasificar"]
    assert len(sin_clasificar) == 2, [li["descripcion"] for li in detalle["lineas"]]

    # Asignación en bloque: solo toca las que están sin clasificar
    nueva = client.post(
        "/etiquetas", headers=h, json={"nombre": "Varios", "categoria_id": cat_mercado["id"]}
    ).json()
    r = client.patch(f"/facturas/{fid}/lineas", headers=h, json={"etiqueta_id": nueva["id"]})
    assert r.status_code == 200, r.text
    tras = {li["descripcion"].split()[0]: li for li in r.json()["lineas"]}
    assert tras["PILAS"]["etiqueta_id"] == nueva["id"]
    assert tras["VELA"]["etiqueta_id"] == nueva["id"]
    assert all(tras[k]["origen"] == "manual" for k in ("PILAS", "VELA"))
    # Lo que el diccionario ya acertó no se pisa
    assert tras["PECHUGA"]["etiqueta_id"] == por_nombre["Carnes"]["id"]
    assert tras["PECHUGA"]["origen"] == "diccionario"

    # Y se aprendió: al re-parsear se reconocen por historial
    r = client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    releidas = {li["descripcion"].split()[0]: li for li in r.json()["lineas"]}
    assert releidas["PILAS"]["origen"] == "historial"
    assert releidas["VELA"]["origen"] == "historial"

    # Sin filtro: se puede sobrescribir todo (incluido lo que acertó el diccionario)
    r = client.patch(f"/facturas/{fid}/lineas", headers=h, json={
        "etiqueta_id": por_nombre["Despensa"]["id"], "solo_sin_clasificar": False,
    })
    assert all(li["etiqueta_id"] == por_nombre["Despensa"]["id"] for li in r.json()["lineas"])

    # Y se puede quitar la etiqueta de todas
    r = client.patch(f"/facturas/{fid}/lineas", headers=h, json={
        "etiqueta_id": None, "solo_sin_clasificar": False,
    })
    assert all(li["etiqueta_id"] is None and li["origen"] == "sin_clasificar" for li in r.json()["lineas"])

    # Con un filtro que no encaja con nada, avisa en vez de fingir que hizo algo
    assert client.patch(
        f"/facturas/{fid}/lineas", headers=h, json={"etiqueta_id": nueva["id"], "solo_sin_clasificar": False,
                                                     "linea_ids": [str(uuid.uuid4())]}
    ).status_code == 400


def test_ocr_confirma_con_categoria_para_toda_la_factura(client, engine):
    """Una compra que el diccionario no conoce no debe quedar sin categoría."""
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    _, h = _registrar(client)
    usuario_id = client.get("/auth/me", headers=h).json()["id"]
    cats = {c["nombre"]: c["id"] for c in client.get("/categorias", headers=h).json()}
    etqs = {e["nombre"]: e["id"] for e in client.get("/etiquetas", headers=h).json()}

    SOLO_DESCONOCIDO = """TIENDA VARIOS
PILAS AA DURACEL 4 UN        7.300
VELA AROMATICA VAINILLA      9.900
TOTAL                       17.200
"""
    Session = sessionmaker(bind=engine)

    def nueva(nombre):
        with Session.begin() as s:
            f = Factura(usuario_id=usuario_id, nombre_archivo=nombre, texto_extraido=SOLO_DESCONOCIDO)
            s.add(f)
            s.flush()
            return str(f.id)

    # 1) Solo la categoría: el gasto cae ahí en vez de quedarse sin categoría
    fid = nueva("varios.txt")
    client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    r = client.post(f"/facturas/{fid}/confirmar", headers=h, json={"categoria_id": cats["Otros gastos"]})
    assert r.status_code == 200, r.text
    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 2
    assert all(t["categoria_id"] == cats["Otros gastos"] for t in txs)
    assert all(t["etiqueta_id"] is None for t in txs)

    # 2) La etiqueta manda: de ella sale la categoría
    fid = nueva("varios2.txt")
    client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    r = client.post(f"/facturas/{fid}/confirmar", headers=h, json={"etiqueta_id": etqs["Ropa"]})
    assert r.status_code == 200, r.text
    nuevas = [t for t in client.get("/transacciones", headers=h).json() if t["etiqueta_id"] == etqs["Ropa"]]
    assert len(nuevas) == 2
    assert all(t["categoria_id"] == cats["Otros gastos"] for t in nuevas)

    # 3) Una categoría ajena no se puede usar
    _, h2 = _registrar(client)
    usuario2 = client.get("/auth/me", headers=h2).json()["id"]
    with Session.begin() as s:
        ajena = Factura(usuario_id=usuario2, nombre_archivo="suya.txt", texto_extraido=SOLO_DESCONOCIDO)
        s.add(ajena)
        s.flush()
        fid_ajena = str(ajena.id)
    client.post(f"/facturas/{fid_ajena}/lineas", headers=h2, json={})
    assert client.post(f"/facturas/{fid_ajena}/confirmar", headers=h2, json={
        "categoria_id": cats["Otros gastos"],
    }).status_code == 404


# --- transferencias entre cuentas propias ---------------------------------- #


def test_transferencia_mueve_dos_cuentas_sin_contaminar_reportes(client):
    """Mover dinero entre cuentas no es ingreso ni gasto: no toca reportes ni flujo."""
    _, h = _registrar(client)
    hoy_ = hoy_app()
    ahorros = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "1000000"}).json()
    diario = client.post("/cuentas", headers=h, json={"nombre": "Diario", "saldo_inicial": "0"}).json()
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado")

    # Un gasto real, para comparar
    client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "100000", "fecha": hoy_.isoformat(),
        "categoria_id": cat["id"], "cuenta_id": diario["id"],
    })

    r = client.post("/transacciones", headers=h, json={
        "tipo": "transferencia", "monto": "500000", "fecha": hoy_.isoformat(),
        "descripcion": "Traslado a la cuenta del día a día",
        "cuenta_id": ahorros["id"], "cuenta_destino_id": diario["id"],
    })
    assert r.status_code == 201, r.text
    assert r.json()["cuenta_destino_id"] == diario["id"]

    # Los saldos: sale de una y entra en la otra
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Ahorros"]["saldo_actual"] == 500000.0
    assert saldos["Ahorros"]["transferencias_enviadas"] == 500000.0
    assert saldos["Ahorros"]["ingresos"] == 0.0 and saldos["Ahorros"]["gastos"] == 0.0
    assert saldos["Diario"]["saldo_actual"] == 400000.0  # +500.000 de la transferencia −100.000 del gasto
    assert saldos["Diario"]["transferencias_recibidas"] == 500000.0
    assert saldos["Diario"]["gastos"] == 100000.0
    # El total no cambia por mover dinero de un bolsillo a otro
    assert client.get("/cuentas", headers=h).json()["saldo_total"] == 900000.0

    # Ni los reportes ni el flujo de caja la cuentan
    mensual = client.get("/reportes/mensual?meses=6", headers=h).json()
    assert mensual[-1]["ingresos"] == 0.0
    assert mensual[-1]["gastos"] == 100000.0
    flujo = client.get("/flujo-caja?meses=3", headers=h).json()
    assert flujo["total_ingresos"] == 0.0
    diag = client.get("/saldos/diagnostico", headers=h).json()
    assert diag["gastos_mes"] == 100000.0 and diag["ingresos_mes"] == 0.0
    # El desglose por categoría tampoco la muestra
    categorias = client.get(f"/reportes/categorias?mes={hoy_.strftime('%Y-%m')}", headers=h).json()
    assert all(c["tipo"] == "gasto" for c in categorias)
    assert not any(c["categoria"] == "Sin categoría" for c in categorias)


def test_transferencia_reglas_de_validacion(client):
    """Una transferencia exige dos cuentas distintas, del usuario y de la misma moneda."""
    _, h = _registrar(client)
    a = client.post("/cuentas", headers=h, json={"nombre": "A", "saldo_inicial": "0"}).json()
    b = client.post("/cuentas", headers=h, json={"nombre": "B", "saldo_inicial": "0"}).json()
    usd = client.post("/cuentas", headers=h, json={"nombre": "USD", "moneda": "USD", "saldo_inicial": "0"}).json()
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Mercado")
    hoy_ = hoy_app().isoformat()

    def enviar(**extra):
        cuerpo = {"tipo": "transferencia", "monto": "1000", "fecha": hoy_,
                  "cuenta_id": a["id"], "cuenta_destino_id": b["id"], **extra}
        return client.post("/transacciones", headers=h, json=cuerpo)

    # Sin destino, o con el mismo origen y destino
    assert client.post("/transacciones", headers=h, json={
        "tipo": "transferencia", "monto": "1000", "fecha": hoy_, "cuenta_id": a["id"],
    }).status_code == 422
    assert enviar(cuenta_destino_id=a["id"]).status_code == 422
    # Con categoría, tarjeta o etiqueta (no es un gasto que se clasifique)
    assert enviar(categoria_id=cat["id"]).status_code == 422
    # Entre monedas distintas
    assert enviar(cuenta_destino_id=usd["id"]).status_code == 422
    # Y un gasto normal no puede llevar cuenta de destino
    assert client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "1000", "fecha": hoy_, "cuenta_destino_id": b["id"],
    }).status_code == 422

    # Cuentas de otro usuario
    _, h2 = _registrar(client)
    assert client.post("/transacciones", headers=h2, json={
        "tipo": "transferencia", "monto": "1000", "fecha": hoy_,
        "cuenta_id": a["id"], "cuenta_destino_id": b["id"],
    }).status_code == 404

    # Al convertir un gasto en transferencia se valida el estado resultante
    gasto = client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "5000", "fecha": hoy_, "categoria_id": cat["id"], "cuenta_id": a["id"],
    }).json()
    r = client.patch(f"/transacciones/{gasto['id']}", headers=h, json={"tipo": "transferencia"})
    assert r.status_code == 422, "faltan la cuenta de destino y sobra la categoría"
    r = client.patch(f"/transacciones/{gasto['id']}", headers=h, json={
        "tipo": "transferencia", "cuenta_destino_id": b["id"], "categoria_id": None,
    })
    assert r.status_code == 200, r.text
    assert r.json()["cuenta_destino_id"] == b["id"] and r.json()["categoria_id"] is None
    # Y el saldo ya refleja la conversión
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["A"]["saldo_actual"] == -5000.0
    assert saldos["B"]["saldo_actual"] == 5000.0


# --- copiar las etiquetas de otra categoría (Casa 2 con lo de Casa 1) ------- #


def _casa(client, h, nombre, tipo="gasto"):
    return client.post("/categorias", headers=h, json={"nombre": nombre, "tipo": tipo}).json()


def test_copiar_etiquetas_de_otra_categoria(client):
    """Crear «Casa 2» con las etiquetas de «Casa 1» sin volver a teclearlas."""
    _, h = _registrar(client)
    c1, c2 = _casa(client, h, "Casa 1"), _casa(client, h, "Casa 2")

    def etq(nombre, cat_id, padre_id=None):
        return client.post("/etiquetas", headers=h, json={
            "nombre": nombre, "categoria_id": cat_id, "padre_id": padre_id,
        }).json()

    servicios = etq("Servicios", c1["id"])
    etq("Internet", c1["id"], servicios["id"])
    etq("Agua", c1["id"], servicios["id"])
    aseo = etq("Aseo", c1["id"])
    etq("Señora del aseo", c1["id"], aseo["id"])
    etq("Arriendo", c1["id"])

    def en(cat_id):
        return [e for e in client.get("/etiquetas", headers=h).json() if e["categoria_id"] == cat_id]

    # 1) Previsualización: enseña el plan y NO toca el árbol
    r = client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h,
                    json={"origen_id": c1["id"], "previsualizar": True})
    assert r.status_code == 200, r.text
    plan = r.json()
    assert plan["previsualizar"] is True and plan["total_creadas"] == 6
    assert "Servicios › Internet" in plan["plan"] and "Arriendo" in plan["plan"]
    assert plan["creadas"] == []
    assert en(c2["id"]) == [], "la previsualización no debe crear nada"

    # 2) Copiar de verdad, conservando el anidamiento
    r = client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h, json={"origen_id": c1["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["total_creadas"] == 6 and r.json()["omitidas"] == []
    copiadas = {e["nombre"]: e for e in en(c2["id"])}
    assert set(copiadas) == {"Servicios", "Internet", "Agua", "Aseo", "Señora del aseo", "Arriendo"}
    assert copiadas["Internet"]["padre_id"] == copiadas["Servicios"]["id"]
    assert copiadas["Señora del aseo"]["padre_id"] == copiadas["Aseo"]["id"]
    assert all(e["categoria_id"] == c2["id"] for e in en(c2["id"]))
    assert copiadas["Servicios"]["id"] != servicios["id"], "es una copia, no la misma etiqueta"

    # 3) Idempotente: repetirlo no duplica nada
    r = client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h, json={"origen_id": c1["id"]})
    assert r.json()["total_creadas"] == 0
    assert sorted(r.json()["omitidas"]) == sorted([
        "Servicios", "Servicios › Internet", "Servicios › Agua",
        "Aseo", "Aseo › Señora del aseo", "Arriendo",
    ])
    assert len(en(c2["id"])) == 6

    # 4) Lo nuevo de Casa 1 se añade; y bajo una raíz que ya existe, sus hijas que falten
    etq("Luz", c1["id"])
    c3 = _casa(client, h, "Casa 3")
    etq("Servicios", c3["id"])  # la raíz ya está, pero sin hijas
    r = client.post(f"/categorias/{c3['id']}/copiar-etiquetas", headers=h, json={"origen_id": c1["id"]})
    assert {e["nombre"] for e in r.json()["creadas"]} == {
        "Internet", "Agua", "Aseo", "Señora del aseo", "Arriendo", "Luz",
    }
    assert r.json()["omitidas"] == ["Servicios"]
    internet_c3 = next(e for e in en(c3["id"]) if e["nombre"] == "Internet")
    raiz_c3 = next(e for e in en(c3["id"]) if e["nombre"] == "Servicios")
    assert internet_c3["padre_id"] == raiz_c3["id"]

    # 5) Las etiquetas copiadas sirven para clasificar de verdad
    hoy_ = hoy_app().isoformat()
    tx = client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "90000", "fecha": hoy_,
        "descripcion": "Internet del mes", "etiqueta_id": copiadas["Internet"]["id"],
        "categoria_id": c2["id"],
    }).json()
    assert tx["etiqueta_id"] == copiadas["Internet"]["id"]
    assert tx["categoria_id"] == c2["id"]


def test_copiar_etiquetas_validaciones(client):
    """Misma categoría, tipos distintos y categorías de otro usuario."""
    _, h = _registrar(client)
    c1 = _casa(client, h, "Casa 1")
    c2 = _casa(client, h, "Casa 2")
    ingreso = _casa(client, h, "Ingresos extra", tipo="ingreso")

    # Misma categoría como origen y destino
    assert client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h, json={
        "origen_id": c2["id"],
    }).status_code == 422
    # Mezclar gastos con ingresos
    assert client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h, json={
        "origen_id": ingreso["id"],
    }).status_code == 422
    # Una categoría de otro usuario no existe para mí
    _, h2 = _registrar(client)
    assert client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h2, json={
        "origen_id": c1["id"],
    }).status_code == 404
    assert client.post(f"/categorias/{c1['id']}/copiar-etiquetas", headers=h2, json={
        "origen_id": c2["id"],
    }).status_code == 404
    # Y una categoría de origen inventada
    assert client.post(f"/categorias/{c2['id']}/copiar-etiquetas", headers=h, json={
        "origen_id": str(uuid.uuid4()),
    }).status_code == 404


# --- un movimiento que se repite (recurrente) u ocasional ------------------- #


def test_transaccion_recurrente_crea_el_compromiso(client):
    """«Se repite»: la transacción es el pago de este periodo y nace el compromiso."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "3000000"}).json()
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Vivienda")
    etq = client.post("/etiquetas", headers=h, json={"nombre": "Arriendo", "categoria_id": cat["id"]}).json()
    hoy_ = hoy_app()

    r = client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "1500000", "fecha": hoy_.isoformat(),
        "descripcion": "Arriendo", "categoria_id": cat["id"], "etiqueta_id": etq["id"],
        "cuenta_id": cuenta["id"],
        "recurrencia": {"periodicidad": "mensual"},
    })
    assert r.status_code == 201, r.text
    tx = r.json()
    assert tx["suscripcion_id"] is not None, "la transacción queda enlazada al compromiso"
    # Sigue siendo el gasto de este periodo, con su cuenta
    assert tx["cuenta_id"] == cuenta["id"]

    sups = client.get("/suscripciones", headers=h).json()
    assert len(sups) == 1
    sub = sups[0]
    assert sub["nombre"] == "Arriendo" and float(sub["monto"]) == 1500000.0
    assert sub["periodicidad"] == "mensual" and sub["estado"] == "activa"
    assert sub["categoria_id"] == cat["id"] and sub["etiqueta_id"] == etq["id"]
    # El día sale de la fecha: el compromiso apunta al MISMO día del mes siguiente,
    # recortado al último día de ese mes cuando no existe (31 de enero -> 28 de febrero).
    # Antes el test fijaba el día 28 a mano y solo pasaba hasta el día 28 del mes.
    mes_esperado = hoy_.month % 12 + 1
    anio_esperado = hoy_.year + (1 if hoy_.month == 12 else 0)
    esperado = date(
        anio_esperado, mes_esperado,
        min(hoy_.day, calendar.monthrange(anio_esperado, mes_esperado)[1]),
    )
    assert sub["proximo_pago"] == esperado.isoformat()
    assert sub["cuenta_id"] == cuenta["id"], "sin cuenta, el gasto del mes que viene no movería el saldo"

    # Y la cuenta ya descontó este periodo
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Ahorros"]["saldo_actual"] == 1500000.0


def test_recurrente_no_duplica_el_periodo_y_sigue_generando(client, engine):
    """El compromiso apunta al siguiente periodo: el job no duplica el de ahora."""
    from sqlalchemy.orm import sessionmaker

    from app.recurrencia import procesar_suscripciones

    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Diario", "saldo_inicial": "1000000"}).json()
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Suscripciones")
    hoy_ = hoy_app()

    r = client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "44900", "fecha": hoy_.isoformat(),
        "descripcion": "Streaming", "categoria_id": cat["id"], "cuenta_id": cuenta["id"],
        "recurrencia": {"periodicidad": "semanal"},
    })
    assert r.status_code == 201, r.text

    sf = sessionmaker(bind=engine, expire_on_commit=False)
    # Hoy no hay nada vencido: no se duplica el periodo que acabo de registrar
    with sf.begin() as s:
        assert procesar_suscripciones(s, hoy_) == 0
    assert len(client.get("/transacciones", headers=h).json()) == 1

    # A la semana siguiente genera uno, y solo uno, con su cuenta
    siguiente = hoy_ + timedelta(days=7)
    with sf.begin() as s:
        assert procesar_suscripciones(s, siguiente) == 1
        assert procesar_suscripciones(s, siguiente) == 0  # idempotente

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 2
    generada = next(t for t in txs if t["fecha"] == siguiente.isoformat())
    assert generada["suscripcion_id"] is not None, "queda enlazada al compromiso"
    assert generada["cuenta_id"] == cuenta["id"], "y mueve la cuenta, no queda «sin cuenta»"
    # Los dos periodos descontaron del saldo
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Diario"]["saldo_actual"] == 1000000.0 - 2 * 44900.0


def test_transaccion_recurrente_ingreso(client):
    """Un ingreso que se repite crea su compromiso con la cuenta donde entra."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Nómina", "saldo_inicial": "0"}).json()
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Salario")
    hoy_ = hoy_app()

    r = client.post("/transacciones", headers=h, json={
        "tipo": "ingreso", "monto": "5000000", "fecha": hoy_.isoformat(),
        "descripcion": "Salario", "categoria_id": cat["id"], "cuenta_id": cuenta["id"],
        "recurrencia": {"periodicidad": "mensual"},
    })
    assert r.status_code == 201, r.text
    assert r.json()["ingreso_recurrente_id"] is not None

    ingresos = client.get("/ingresos-recurrentes", headers=h).json()
    assert len(ingresos) == 1
    ing = ingresos[0]
    assert ing["nombre"] == "Salario" and float(ing["monto"]) == 5000000.0
    assert ing["periodicidad"] == "mensual" and ing["dia"] == hoy_.day
    assert ing["cuenta_id"] == cuenta["id"]
    assert ing["proxima_ejecucion"] > hoy_.isoformat()
    # Y el ingreso de este periodo ya entró en la cuenta
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Nómina"]["saldo_actual"] == 5000000.0


def test_recurrente_validaciones(client):
    """Transferencias, periodicidades que no encajan y referencias ajenas."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "A", "saldo_inicial": "0"}).json()
    otra = client.post("/cuentas", headers=h, json={"nombre": "B", "saldo_inicial": "0"}).json()
    hoy_ = hoy_app().isoformat()

    def enviar(**extra):
        return client.post("/transacciones", headers=h, json={
            "tipo": "gasto", "monto": "1000", "fecha": hoy_, "cuenta_id": cuenta["id"], **extra,
        })

    # Una transferencia no puede ser recurrente (todavía): falta de qué cuenta sale
    assert enviar(
        tipo="transferencia", cuenta_destino_id=otra["id"],
        recurrencia={"periodicidad": "mensual"},
    ).status_code == 422
    # Periodicidad que no encaja con el tipo de movimiento
    r = enviar(recurrencia={"periodicidad": "diario"})
    assert r.status_code == 422 and "gasto recurrente" in r.json()["detail"]
    r = enviar(tipo="ingreso", recurrencia={"periodicidad": "trimestral"})
    assert r.status_code == 422 and "ingreso recurrente" in r.json()["detail"]

    # Una categoría, etiqueta, cuenta o compromiso de otro usuario no se puede usar
    _, h2 = _registrar(client)
    cat_ajena = next(c for c in client.get("/categorias", headers=h2).json() if c["nombre"] == "Vivienda")
    assert client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "1000", "fecha": hoy_, "categoria_id": cat_ajena["id"],
    }).status_code == 404
    sub_ajena = client.post("/suscripciones", headers=h2, json={"nombre": "Suya", "monto": "1000"}).json()
    assert client.post("/transacciones", headers=h, json={
        "tipo": "gasto", "monto": "1000", "fecha": hoy_, "suscripcion_id": sub_ajena["id"],
    }).status_code == 404
    # Y los compromisos tampoco aceptan cuentas ajenas
    assert client.post("/suscripciones", headers=h, json={
        "nombre": "Mía", "monto": "1000", "cuenta_id": "00000000-0000-0000-0000-000000000000",
    }).status_code == 404
    assert client.post("/ingresos-recurrentes", headers=h, json={
        "nombre": "Mío", "monto": "1000", "periodicidad": "mensual", "dia": 5,
        "cuenta_id": "00000000-0000-0000-0000-000000000000",
    }).status_code == 404


# --- pagar la tarjeta de crédito (baja la cuenta y la deuda) ---------------- #


def test_pago_de_tarjeta_baja_la_cuenta_y_la_deuda(client):
    """El pago mueve la cuenta, baja la deuda y **no** cuenta como gasto."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "5000000"}).json()
    tarjeta = client.post("/tarjetas", headers=h, json={
        "nombre": "Visa", "tipo": "credito", "banco": "Bogotá",
    }).json()
    hoy_ = hoy_app().isoformat()

    # Lo que dice el extracto
    client.post(f"/tarjetas/{tarjeta['id']}/deudas", headers=h, json={"moneda": "COP", "monto": "1000000"})
    antes = client.get(f"/tarjetas/{tarjeta['id']}", headers=h).json()
    assert antes["deuda_por_moneda"]["COP"] == 1000000.0

    # Pago parcial: la deuda queda en el remanente
    r = client.post(f"/tarjetas/{tarjeta['id']}/pagos", headers=h, json={
        "cuenta_id": cuenta["id"], "monto": "400000", "moneda": "COP", "fecha": hoy_,
        "notas": "Pago mínimo",
    })
    assert r.status_code == 201, r.text
    tras = r.json()
    assert tras["deuda_por_moneda"]["COP"] == 600000.0
    assert tras["extracto_por_moneda"]["COP"] == 1000000.0
    assert tras["pagos_por_moneda"]["COP"] == 400000.0
    assert tras["deuda_total_cop"] == 600000.0
    assert len(tras["pagos"]) == 1
    pago = tras["pagos"][0]
    assert pago["cuenta_id"] == cuenta["id"] and pago["transaccion_id"] is not None

    # La cuenta ya descontó el pago
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Ahorros"]["saldo_actual"] == 4600000.0

    # El movimiento es una transferencia, NO un gasto: si fuera gasto, el consumo se
    # contaría dos veces (al comprar y al pagar)
    tx = next(t for t in client.get("/transacciones", headers=h).json() if t["tarjeta_id"] == tarjeta["id"])
    assert tx["tipo"] == "transferencia"
    assert tx["cuenta_id"] == cuenta["id"] and tx["cuenta_destino_id"] is None
    mes = hoy_[:7]
    mensual = client.get("/reportes/mensual?meses=6", headers=h).json()
    assert mensual[-1]["gastos"] == 0.0, "pagar la tarjeta no es un gasto"
    categorias = client.get(f"/reportes/categorias?mes={mes}", headers=h).json()
    assert categorias == []

    # Y deshacer el pago devuelve todo
    assert client.delete(f"/tarjetas/{tarjeta['id']}/pagos/{pago['id']}", headers=h).status_code == 204
    devuelta = client.get(f"/tarjetas/{tarjeta['id']}", headers=h).json()
    assert devuelta["deuda_por_moneda"]["COP"] == 1000000.0
    assert devuelta["pagos"] == []
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Ahorros"]["saldo_actual"] == 5000000.0
    assert client.get("/transacciones", headers=h).json() == []


def test_extracto_nuevo_no_suma_el_anterior_ni_el_pago(client):
    """La deuda es un **nivel**: manda el último extracto, no la suma de todos."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "5000000"}).json()
    tarjeta = client.post("/tarjetas", headers=h, json={"nombre": "Visa", "tipo": "credito"}).json()

    # Extracto de septiembre
    client.post(f"/tarjetas/{tarjeta['id']}/deudas", headers=h, json={
        "moneda": "COP", "monto": "1000000", "fecha": "2026-09-05",
    })
    antes = client.get(f"/tarjetas/{tarjeta['id']}", headers=h).json()
    assert antes["deuda_por_moneda"]["COP"] == 1000000.0

    # Pago del 20 de septiembre: baja la deuda vigente
    client.post(f"/tarjetas/{tarjeta['id']}/pagos", headers=h, json={
        "cuenta_id": cuenta["id"], "monto": "300000", "moneda": "COP", "fecha": "2026-09-20",
    })
    assert client.get(f"/tarjetas/{tarjeta['id']}", headers=h).json()["deuda_por_moneda"]["COP"] == 700000.0

    # Extracto de octubre (ya incluye el pago): pasa a ser el nivel y el pago NO se resta otra vez
    client.post(f"/tarjetas/{tarjeta['id']}/deudas", headers=h, json={
        "moneda": "COP", "monto": "800000", "fecha": "2026-10-05",
    })
    tras = client.get(f"/tarjetas/{tarjeta['id']}", headers=h).json()
    assert tras["deuda_por_moneda"]["COP"] == 800000.0, "no se suma el extracto anterior ni se resta dos veces el pago"
    assert tras["pagos_por_moneda"] == {}, "el pago es anterior al extracto vigente"
    assert tras["extracto_por_moneda"]["COP"] == 800000.0

    # Registrar dos veces el mismo extracto tampoco duplica (era el bug: se sumaban)
    client.post(f"/tarjetas/{tarjeta['id']}/deudas", headers=h, json={
        "moneda": "COP", "monto": "800000", "fecha": "2026-10-05",
    })
    assert client.get(f"/tarjetas/{tarjeta['id']}", headers=h).json()["deuda_por_moneda"]["COP"] == 800000.0


def test_pago_de_tarjeta_validaciones(client):
    """No se puede pagar más de lo debido, ni una de débito, ni con datos ajenos."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "5000000"}).json()
    usd = client.post("/cuentas", headers=h, json={"nombre": "USD", "moneda": "USD", "saldo_inicial": "0"}).json()
    visa = client.post("/tarjetas", headers=h, json={"nombre": "Visa", "tipo": "credito"}).json()
    debito = client.post("/tarjetas", headers=h, json={
        "nombre": "Débito", "tipo": "debito", "cuenta_id": cuenta["id"],
    }).json()

    def pagar(monto="100000", tarjeta=None, **extra):
        return client.post(f"/tarjetas/{(tarjeta or visa)['id']}/pagos", headers=h, json={
            "cuenta_id": cuenta["id"], "monto": monto, "moneda": "COP", **extra,
        })

    # Sin deuda registrada no hay nada que pagar (y el mensaje dice qué hacer)
    r = pagar()
    assert r.status_code == 422 and "no tiene deuda registrada" in r.json()["detail"]

    client.post(f"/tarjetas/{visa['id']}/deudas", headers=h, json={"moneda": "COP", "monto": "100000"})
    # Pagar más de lo que se debe
    r = pagar(monto="100001")
    assert r.status_code == 422 and "supera la deuda" in r.json()["detail"]
    # Otra moneda que no tiene deuda
    assert pagar(monto="1000", moneda="USD").status_code == 422
    # La cuenta y el pago deben ser de la misma moneda
    r = pagar(monto="1000", moneda="COP", cuenta_id=usd["id"])
    assert r.status_code == 422 and "monedas" in r.json()["detail"] or r.status_code == 422
    # Una tarjeta de débito no genera deuda
    r = pagar(tarjeta=debito)
    assert r.status_code == 422 and "débito" in r.json()["detail"]

    # Cuentas y tarjetas de otro usuario
    _, h2 = _registrar(client)
    assert client.post(f"/tarjetas/{visa['id']}/pagos", headers=h2, json={
        "cuenta_id": cuenta["id"], "monto": "1000", "moneda": "COP",
    }).status_code == 404
    assert client.post(f"/tarjetas/{visa['id']}/pagos", headers=h, json={
        "cuenta_id": "00000000-0000-0000-0000-000000000000", "monto": "1000", "moneda": "COP",
    }).status_code == 404

    # La transferencia a una tarjeta también se puede hacer a mano, pero solo a crédito
    hoy_ = hoy_app().isoformat()
    r = client.post("/transacciones", headers=h, json={
        "tipo": "transferencia", "monto": "1000", "fecha": hoy_,
        "cuenta_id": cuenta["id"], "tarjeta_id": debito["id"],
    })
    assert r.status_code == 422 and "débito" in r.json()["detail"]
    # Y una transferencia no puede tener dos destinos a la vez
    assert client.post("/transacciones", headers=h, json={
        "tipo": "transferencia", "monto": "1000", "fecha": hoy_,
        "cuenta_id": cuenta["id"], "tarjeta_id": visa["id"], "cuenta_destino_id": usd["id"],
    }).status_code == 422


# --- /health comprueba la base -------------------------------------------- #


def test_health_ok(client):
    """Con la base en pie, el estado es ok y lo dice explícitamente."""
    r = client.get("/health")
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "ok", "app": "konta", "base": "ok", "error": None}


def test_health_503_si_la_base_no_responde(client):
    """Si la base no contesta, 503 (y sin filtrar la cadena de conexión)."""
    from sqlalchemy.exc import OperationalError

    from app.deps import get_db
    from app.main import app

    class SesionCaida:
        def execute(self, *args, **kwargs):
            raise OperationalError(
                "SELECT 1", {}, Exception("could not connect to server: Connection refused")
            )

    app.dependency_overrides[get_db] = lambda: SesionCaida()
    try:
        r = client.get("/health")
        assert r.status_code == 503, r.text
        cuerpo = r.json()
        assert cuerpo["status"] == "error" and cuerpo["base"] == "sin conexión"
        assert cuerpo["error"] == "OperationalError"
        assert "Connection refused" not in r.text, "el detalle no se filtra al exterior"
    finally:
        app.dependency_overrides.pop(get_db, None)

    # Y al quitar el override vuelve a estar sano
    assert client.get("/health").status_code == 200


def test_health_no_pide_token(client):
    """Lo consulta el orquestador, que no tiene credenciales de usuario."""
    assert client.get("/health").status_code == 200
    assert client.get("/transacciones").status_code == 401


# --- reglas de OCR aprendidas: verlas, corregirlas y borrarlas -------------- #


def _factura_con(client, engine, h, texto):
    from sqlalchemy.orm import sessionmaker

    from app.models import Factura

    usuario_id = client.get("/auth/me", headers=h).json()["id"]
    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        f = Factura(usuario_id=usuario_id, nombre_archivo="r.txt", texto_extraido=texto)
        s.add(f)
        s.flush()
        return str(f.id)


def test_reglas_ocr_crud_y_deshacer_el_aprendizaje(client, engine):
    """Lo que el clasificador aprende se puede ver, corregir y deshacer."""
    _, h = _registrar(client)
    etqs = {e["nombre"]: e for e in client.get("/etiquetas", headers=h).json()}

    # Al principio no sabe nada
    assert client.get("/reglas-ocr", headers=h).json() == []

    # 1) Crear una regla a mano (sin esperar a corregir una línea)
    r = client.post("/reglas-ocr", headers=h, json={
        "patron": "  panela  cuadrada ", "etiqueta_id": etqs["Despensa"]["id"],
    })
    assert r.status_code == 201, r.text
    regla = r.json()
    # El patrón se normaliza igual que al aprender
    assert regla["patron"] == "PANELA CUADRADA"
    assert regla["etiqueta_nombre"] == "Despensa" and regla["categoria_nombre"] == "Mercado"
    assert regla["veces_usada"] == 1
    assert client.get("/reglas-ocr", headers=h).json()[0]["id"] == regla["id"]

    # Y sirve: un recibo con ese artículo se clasifica por historial
    fid = _factura_con(client, engine, h, "PANELA CUADRADA 500G        3.500\n")
    lineas = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()["lineas"]
    assert lineas[0]["origen"] == "historial"
    assert lineas[0]["etiqueta_id"] == etqs["Despensa"]["id"]

    # 2) Corregirla: el mismo artículo ahora va a otra etiqueta
    r = client.patch(f"/reglas-ocr/{regla['id']}", headers=h, json={
        "etiqueta_id": etqs["Frutas y verduras"]["id"],
    })
    assert r.status_code == 200, r.text
    assert r.json()["etiqueta_nombre"] == "Frutas y verduras"
    fid = _factura_con(client, engine, h, "PANELA CUADRADA 500G        3.500\n")
    lineas = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()["lineas"]
    assert lineas[0]["etiqueta_id"] == etqs["Frutas y verduras"]["id"]

    # 3) Deshacer el aprendizaje: vuelve a no saber nada
    assert client.delete(f"/reglas-ocr/{regla['id']}", headers=h).status_code == 204
    assert client.get("/reglas-ocr", headers=h).json() == []
    fid = _factura_con(client, engine, h, "PANELA CUADRADA 500G        3.500\n")
    lineas = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()["lineas"]
    assert lineas[0]["origen"] != "historial", "sin regla, el artículo ya no se reconoce de memoria"

    # 4) El flujo normal sigue aprendiendo (corregir una línea crea la regla)
    fid = _factura_con(client, engine, h, "COSA RARA DEL SUPER       9.900\n")
    linea = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()["lineas"][0]
    client.patch(f"/facturas/{fid}/lineas/{linea['id']}", headers=h, json={
        "etiqueta_id": etqs["Carnes"]["id"],
    })
    aprendidas = client.get("/reglas-ocr", headers=h).json()
    assert len(aprendidas) == 1
    assert aprendidas[0]["patron"] == "COSA RARA DEL SUPER"
    assert aprendidas[0]["etiqueta_nombre"] == "Carnes"
    assert aprendidas[0]["veces_usada"] == 1


def test_reglas_ocr_validaciones_y_aislamiento(client):
    """Patrones duplicados o vacíos, etiquetas ajenas y reglas de otro usuario."""
    _, h = _registrar(client)
    etq = next(e for e in client.get("/etiquetas", headers=h).json() if e["nombre"] == "Carnes")
    base = {"patron": "PECHUGA POLLO", "etiqueta_id": etq["id"]}

    r = client.post("/reglas-ocr", headers=h, json=base)
    assert r.status_code == 201, r.text
    regla_id = r.json()["id"]

    # Duplicado (aunque cambie el formato del texto, el patrón normalizado es el mismo)
    r = client.post("/reglas-ocr", headers=h, json={**base, "patron": "pechuga  pollo"})
    assert r.status_code == 400 and "Ya existe" in r.json()["detail"]
    # Patrón que queda vacío al normalizar (solo códigos y símbolos)
    assert client.post("/reglas-ocr", headers=h, json={
        "patron": "  12.345  ", "etiqueta_id": etq["id"],
    }).status_code == 422
    # Etiqueta de otro usuario
    _, h2 = _registrar(client)
    etq2 = next(e for e in client.get("/etiquetas", headers=h2).json() if e["nombre"] == "Carnes")
    assert client.post("/reglas-ocr", headers=h, json={
        "patron": "OTRA COSA", "etiqueta_id": etq2["id"],
    }).status_code == 404
    # Y no puedo tocar ni ver las reglas del otro
    assert client.get(f"/reglas-ocr/{regla_id}", headers=h2).status_code == 404
    assert client.patch(f"/reglas-ocr/{regla_id}", headers=h2, json={
        "etiqueta_id": etq2["id"],
    }).status_code == 404
    assert client.delete(f"/reglas-ocr/{regla_id}", headers=h2).status_code == 404

    # Cambiar el patrón a uno que ya tengo da 400
    otra = client.post("/reglas-ocr", headers=h, json={
        "patron": "ARROZ DIANA", "etiqueta_id": etq["id"],
    }).json()
    assert client.patch(f"/reglas-ocr/{otra['id']}", headers=h, json={
        "patron": "PECHUGA POLLO",
    }).status_code == 400
    # Y renombrarlo a algo libre funciona
    assert client.patch(f"/reglas-ocr/{otra['id']}", headers=h, json={
        "patron": "ARROZ DIANA 500G",
    }).status_code == 200


# --- confirmar el recibo como un solo gasto -------------------------------- #


def test_confirmar_recibo_como_un_solo_gasto(client, engine):
    """Una compra de tres cosas, un solo movimiento (con las líneas como detalle)."""
    _, h = _registrar(client)
    cuenta = client.post("/cuentas", headers=h, json={"nombre": "Ahorros", "saldo_inicial": "0"}).json()
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Otros gastos")
    # «Ropa» ya viene de fábrica: es una de las etiquetas del diccionario
    etq = next(e for e in client.get("/etiquetas", headers=h).json() if e["nombre"] == "Ropa")

    fid = _factura_con(client, engine, h, ROPA)
    detalle = client.post(f"/facturas/{fid}/lineas", headers=h, json={}).json()
    assert len(detalle["lineas"]) == 3
    suma = sum((Decimal(li["valor_total"]) for li in detalle["lineas"]), Decimal("0"))
    assert suma == Decimal("499700")

    # Un solo gasto, con la etiqueta de respaldo y la cuenta
    r = client.post(f"/facturas/{fid}/confirmar-total", headers=h, json={
        "cuenta_id": cuenta["id"], "etiqueta_id": etq["id"], "descripcion": "Ropa de temporada",
    })
    assert r.status_code == 200, r.text
    detalle = r.json()
    # Todas las líneas quedan enlazadas a la MISMA transacción (el detalle no se pierde)
    ids = {li["transaccion_id"] for li in detalle["lineas"]}
    assert len(ids) == 1 and None not in ids
    # Y la factura queda asociada a ese gasto
    assert detalle["transaccion_id"] == next(iter(ids))

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 1, "una sola transacción, no tres"
    tx = txs[0]
    assert float(tx["monto"]) == 499700.0, "el total es la suma de las líneas"
    assert tx["descripcion"] == "Ropa de temporada"
    assert tx["categoria_id"] == cat["id"] and tx["etiqueta_id"] == etq["id"]
    assert tx["cuenta_id"] == cuenta["id"]
    assert tx["suscripcion_id"] is None

    # La cuenta descontó el total una sola vez
    saldos = {c["nombre"]: c for c in client.get("/cuentas", headers=h).json()["cuentas"]}
    assert saldos["Ahorros"]["saldo_actual"] == -499700.0
    mensual = client.get("/reportes/mensual?meses=6", headers=h).json()
    assert mensual[-1]["gastos"] == 499700.0

    # Idempotente: ya no quedan líneas pendientes
    assert client.post(f"/facturas/{fid}/confirmar-total", headers=h, json={}).status_code == 400


def test_solo_gasto_con_monto_del_recibo_y_sin_descripcion(client, engine):
    """El monto se puede forzar al total del recibo; sin descripción, se propone una."""
    _, h = _registrar(client)
    cat = next(c for c in client.get("/categorias", headers=h).json() if c["nombre"] == "Otros gastos")

    # 1) Forzando el monto (el recibo dice 500.000 y las líneas suman 499.700)
    fid = _factura_con(client, engine, h, ROPA)
    client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    r = client.post(f"/facturas/{fid}/confirmar-total", headers=h, json={
        "categoria_id": cat["id"], "monto": "500000",
    })
    assert r.status_code == 200, r.text
    tx = client.get("/transacciones", headers=h).json()[0]
    assert float(tx["monto"]) == 500000.0
    # Sin descripción y con 3 líneas, se propone una legible
    assert tx["descripcion"] == "Compra de 3 artículos"
    # Y con categoría de respaldo (sin etiqueta), el gasto no queda huérfano
    assert tx["categoria_id"] == cat["id"] and tx["etiqueta_id"] is None

    # 2) Con una sola línea, la descripción es el propio artículo
    fid = _factura_con(client, engine, h, "PANELA CUADRADA 500G        3.500\n")
    client.post(f"/facturas/{fid}/lineas", headers=h, json={})
    r = client.post(f"/facturas/{fid}/confirmar-total", headers=h, json={"categoria_id": cat["id"]})
    assert r.status_code == 200, r.text
    nueva = [t for t in client.get("/transacciones", headers=h).json() if float(t["monto"]) == 3500.0]
    assert nueva[0]["descripcion"] == "PANELA CUADRADA 500G"

    # 3) Aislamiento: la factura de otro no existe para mí
    _, h2 = _registrar(client)
    assert client.post(f"/facturas/{fid}/confirmar-total", headers=h2, json={}).status_code == 404
    # 4) Y una cuenta ajena se rechaza
    usuario2 = client.get("/auth/me", headers=h2).json()["id"]
    from sqlalchemy.orm import sessionmaker

    from app.models import Cuenta, Factura

    Session = sessionmaker(bind=engine)
    with Session.begin() as s:
        cta = Cuenta(usuario_id=usuario2, nombre="Suya", saldo_inicial=0)
        s.add(cta)
        s.flush()
        cta_id = str(cta.id)
        f = Factura(usuario_id=usuario2, nombre_archivo="x.txt", texto_extraido=ROPA)
        s.add(f)
        s.flush()
        fid2 = str(f.id)
    client.post(f"/facturas/{fid2}/lineas", headers=h2, json={})
    assert client.post(f"/facturas/{fid2}/confirmar-total", headers=h2, json={
        "cuenta_id": cta_id,
    }).status_code == 200
    # La misma cuenta, desde el otro usuario, no se puede usar
    assert client.post(f"/facturas/{fid2}/confirmar-total", headers=h, json={
        "cuenta_id": cta_id,
    }).status_code == 404


# --- los ENUM de la base y los del código no se separan -------------------- #


def test_los_enums_de_la_base_coinciden_con_los_del_codigo(engine):
    """Guarda contra una deriva que `alembic check` **no** ve.

    Comprobado al recrear un tipo a mano: `alembic check` compara tablas, columnas,
    índices y tipos, pero **no las etiquetas de un ENUM**. Si un valor existe en el
    código y no en la base (o al revés), el check sigue diciendo que no hay deriva y
    el fallo aparece en producción, al insertar justo esa fila. Esto lo cierra.
    """
    from sqlalchemy import text

    from app.models import (
        EstadoSuscripcion,
        Periodicidad,
        PeriodicidadIngreso,
        TipoCategoria,
        TipoTarjeta,
        TipoTransaccion,
    )

    esperados = {
        "tipo_categoria": TipoCategoria,
        "periodicidad": Periodicidad,
        "estado_suscripcion": EstadoSuscripcion,
        "tipo_tarjeta": TipoTarjeta,
        "tipo_transaccion": TipoTransaccion,
        "periodicidad_ingreso": PeriodicidadIngreso,
    }

    with engine.connect() as conn:
        for tipo, enum_py in esperados.items():
            en_bd = {
                fila[0]
                for fila in conn.execute(
                    text(
                        "select enumlabel from pg_enum e "
                        "join pg_type t on t.oid = e.enumtypid "
                        "where t.typname = :tipo"
                    ),
                    {"tipo": tipo},
                )
            }
            en_codigo = {m.value for m in enum_py}
            assert en_bd, f"el tipo {tipo} no existe en la base"
            assert en_bd == en_codigo, (
                f"{tipo}: solo en la base {sorted(en_bd - en_codigo)}, "
                f"solo en el código {sorted(en_codigo - en_bd)}"
            )


def test_borrar_un_aporte_de_una_meta(client):
    """El aporte se puede borrar y el saldo de la meta baja (es lo que hace la UI)."""
    _, h = _registrar(client)
    meta = client.post(
        "/metas", headers=h, json={"nombre": "Viaje", "monto_objetivo": "1000000"}
    ).json()
    client.post(f"/metas/{meta['id']}/aportes", headers=h, json={"monto": "250000"})
    client.post(f"/metas/{meta['id']}/aportes", headers=h, json={"monto": "100000"})

    aportes = client.get(f"/metas/{meta['id']}/aportes", headers=h).json()
    assert len(aportes) == 2
    assert client.get("/metas", headers=h).json()[0]["monto_actual"] == 350000.0

    # Se borra el de 250.000
    a_borrar = next(a for a in aportes if float(a["monto"]) == 250000.0)
    r = client.delete(f"/metas/aportes/{a_borrar['id']}", headers=h)
    assert r.status_code == 204

    quedan = client.get(f"/metas/{meta['id']}/aportes", headers=h).json()
    assert len(quedan) == 1
    assert float(quedan[0]["monto"]) == 100000.0
    # Y el saldo de la meta baja: no es solo un borrado visual
    assert client.get("/metas", headers=h).json()[0]["monto_actual"] == 100000.0

    # Un aporte que no es tuyo no se puede borrar
    _, h2 = _registrar(client)
    assert client.delete(f"/metas/aportes/{quedan[0]['id']}", headers=h2).status_code == 404


def test_editar_y_borrar_un_producto(client):
    """Editar el nombre y la unidad, y borrar el producto (con sus precios)."""
    _, h = _registrar(client)
    prod = client.post(
        "/productos", headers=h, json={"nombre": "Leche", "unidad": "litro"}
    ).json()
    client.post(f"/productos/{prod['id']}/precios", headers=h, json={"tienda": "A", "precio": "4000"})

    # Editar
    editado = client.patch(
        f"/productos/{prod['id']}", headers=h, json={"nombre": "Leche entera", "unidad": "caja"}
    )
    assert editado.status_code == 200, editado.text
    assert editado.json()["nombre"] == "Leche entera"
    assert editado.json()["unidad"] == "caja"
    listado = client.get("/productos", headers=h).json()
    assert [p["nombre"] for p in listado] == ["Leche entera"]

    # Borrar: se lleva sus precios por delante
    assert client.delete(f"/productos/{prod['id']}", headers=h).status_code == 204
    assert client.get("/productos", headers=h).json() == []
    assert client.get(f"/productos/{prod['id']}", headers=h).status_code == 404
    assert client.get(f"/productos/{prod['id']}/comparativo", headers=h).status_code == 404
    assert client.get(f"/productos/{prod['id']}/precios", headers=h).status_code == 404

    # Y no se puede tocar el producto de otro
    otro = client.post("/productos", headers=h, json={"nombre": "Pan"}).json()
    _, h2 = _registrar(client)
    assert client.patch(f"/productos/{otro['id']}", headers=h2, json={"nombre": "X"}).status_code == 404
    assert client.delete(f"/productos/{otro['id']}", headers=h2).status_code == 404
