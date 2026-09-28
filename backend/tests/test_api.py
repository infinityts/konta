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
