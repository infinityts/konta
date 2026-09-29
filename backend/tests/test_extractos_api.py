"""API de extractos: subir, analizar, borrar. Y la contraseña del PDF."""

from __future__ import annotations

import io
from decimal import Decimal

from test_api import _registrar
from test_extractos import _excel_amex


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


def test_subir_extracto_de_excel_y_analizarlo(client):
    _, h = _registrar(client)
    r = _subir(client, h, _excel_amex())
    assert r.status_code == 201, r.text
    datos = r.json()

    assert datos["formato"] == "xlsx"
    assert datos["moneda"] == "COP"
    assert len(datos["movimientos"]) == 6, "2 del periodo por hoja + 2 anteriores"
    assert len([m for m in datos["movimientos"] if m["es_informativo"]]) == 2
    assert datos["conciliacion"], "las comprobaciones quedan guardadas"
    # El desglose que declara el archivo se guarda tal cual
    assert Decimal(str(datos["pago_total"])) == Decimal("5000.00")

    r = client.get(f"/extractos/{datos['id']}/analisis", headers=h)
    assert r.status_code == 200, r.text
    analisis = r.json()

    assert analisis["moneda"] == "COP"
    assert analisis["moneda_extracto"] == "COP"
    # Las compras del periodo en pesos (la de dólares va aparte)
    assert Decimal(str(analisis["compras"])) == Decimal("24900.00")
    # El desglose por moneda convive: pesos y dólares, cada uno con lo suyo
    assert set(analisis["por_moneda"]) == {"COP", "USD"}
    assert Decimal(str(analisis["por_moneda"]["USD"]["compras"])) == Decimal("10.54")
    # El compromiso futuro es el capital de las compras a cuotas
    assert Decimal(str(analisis["compromiso_futuro"]["COP"])) > Decimal("0")
    # A dónde se fue la plata, agrupado
    assert analisis["por_categoria"], "el análisis dice en qué se fue la plata"
    assert analisis["movimientos"] == 4, "solo los del periodo"

    # Pedir otra moneda no inventa una conversión: se dice que no se convierte
    otro = client.get(f"/extractos/{datos['id']}/analisis?moneda=USD", headers=h).json()
    assert otro["moneda"] == "COP", "los totales siguen en la moneda del extracto"
    assert otro["moneda_solicitada"] == "USD"
    assert otro["conversion_aplicada"] is False
    assert any("convertir a USD" in a for a in otro["avisos"])
    assert Decimal(str(otro["compras"])) == Decimal("24900.00")


def test_extracto_protegido_pide_contrasena(client):
    """Un PDF cifrado no se lee sin la contraseña, y con ella sí."""
    from pypdf import PdfWriter

    _, h = _registrar(client)
    escritor = PdfWriter()
    escritor.add_blank_page(width=612, height=792)
    escritor.encrypt("clave-secreta")
    buffer = io.BytesIO()
    escritor.write(buffer)
    pdf = buffer.getvalue()

    r = _subir(client, h, pdf, "protegido.pdf")
    assert r.status_code == 400
    assert "contraseña" in r.json()["detail"].lower()

    r = _subir(client, h, pdf, "protegido.pdf", contrasena="clave-secreta")
    assert r.status_code == 201, r.text
    # Se leyó, pero no había tabla: se avisa en vez de inventar movimientos
    datos = r.json()
    assert datos["movimientos"] == []


def test_extracto_archivo_invalido(client):
    _, h = _registrar(client)
    r = _subir(client, h, b"no soy un extracto", "notas.txt")
    assert r.status_code == 400
    assert "PDF" in r.json()["detail"] or "Excel" in r.json()["detail"]


def test_borrar_extracto(client):
    _, h = _registrar(client)
    datos = _subir(client, h, _excel_amex()).json()
    assert len(client.get("/extractos", headers=h).json()) == 1

    assert client.delete(f"/extractos/{datos['id']}", headers=h).status_code == 204
    assert client.get("/extractos", headers=h).json() == []
    assert client.get(f"/extractos/{datos['id']}", headers=h).status_code == 404


def test_los_extractos_no_se_ven_entre_usuarios(client):
    _, h1 = _registrar(client)
    _, h2 = _registrar(client)
    datos = _subir(client, h1, _excel_amex()).json()
    assert client.get(f"/extractos/{datos['id']}", headers=h2).status_code == 404
    assert client.get("/extractos", headers=h2).json() == []


def test_las_compras_en_divisa_se_convierten_con_la_tasa_del_extracto(client):
    """El total no puede ignorar las compras en dólares… ni inventarles una tasa.

    Se convierte con **la tasa que trae el extracto** (la del día de la compra). Lo que no
    trae tasa se queda fuera del total y se lista, para que el número no mienta.
    """
    import io

    import openpyxl

    _, h = _registrar(client)
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "PESOS"
    hoja.append(["Moneda:", "COP"])
    hoja.append(["Periodo facturado", "17 ago / 15 sep. 2026"])
    hoja.append(["Movimientos durante el periodo"])
    hoja.append(["Número de autorización", "Fecha", "Movimientos", "Valor Movimiento",
                 "Número de cuotas", "Valor cuota/abono", "Saldo pendiente"])
    hoja.append(["1", "11/09/2026", "COMPRA EN PESOS", "100.000,00", "1/1", "100.000,00", "0,00"])
    buffer = io.BytesIO()
    libro.save(buffer)

    r = _subir(client, h, buffer.getvalue())
    assert r.status_code == 201, r.text
    datos = r.json()
    a = client.get(f"/extractos/{datos['id']}/analisis", headers=h).json()
    # Solo hay movimientos en pesos: el total es la suma directa
    assert Decimal(str(a["compras"])) == Decimal("100000.00")
    assert Decimal(str(a["sin_tasa_total"])) == Decimal("0")
