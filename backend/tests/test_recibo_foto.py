"""Recibo **fotografiado**: OCR de una foto, tipo de documento y gasto sin artículos.

El texto de este módulo es el OCR **real** de la foto de un parqueadero (Midas Park,
2026-09-29). Se usa como constante para probar el tratamiento del ruido sin depender de
tesseract: el OCR mete la cabecera y el pie del recibo (NIT, dirección, correo, número de
resolución) y antes de los arreglos eso producía seis «artículos» que no eran artículos.
"""

from __future__ import annotations

from test_api import _pdf_minimo, _registrar

from app.facturas import detectar_fecha, detectar_monto
from app.lineas import detectar_tipo, parsear_lineas

OCR_PARQUEADERO = """Midas Park Ss.AS.
NT 901349195-5
REGIMEN COMUN
Documento equivalente POS
No: POSE-85701
Avenida 6a $ 2110-47
midasparking2gmall.com
3502049720
Fecha: 2026-09-29 10:28:03
Ingreso: 2026-09-29 09:56:56
Matrícula:
Duración: On 30m 19s
Operario: MidasKiosko1
Método de pago: Efectivo
Subtotal: $ 3.445
IVA: $ 655
TOTAL: $ 4.100
Recibido: $ 5.000
: $ 900
c5803054e30fdbeb
278da301374
Ae: consumidor final
) ción: 18764116142437
s por su visital
PARKING
S MAS SAS.
"""


def test_el_monto_y_la_fecha_se_leen_de_la_foto():
    assert detectar_monto(OCR_PARQUEADERO) == 4100
    assert str(detectar_fecha(OCR_PARQUEADERO)) == "2026-09-29"


def test_el_recibo_de_parqueadero_no_inventa_articulos():
    """La cabecera del recibo (NIT, dirección, correo, resolución) no son artículos."""
    arts = parsear_lineas(OCR_PARQUEADERO)
    assert arts == [], [a["descripcion"] for a in arts]
    assert detectar_tipo(OCR_PARQUEADERO, arts) == "parqueadero"


def test_la_cabecera_de_una_foto_no_es_un_articulo():
    """Sin el filtro, «NIT 901349195» o la resolución se colaban como artículos."""
    from decimal import Decimal

    from app.lineas import _linea_plausible

    assert _linea_plausible("Midas Park Ss.AS", Decimal("901349195")) is False  # NIT gigante
    assert _linea_plausible("midasparking2gmall.com", Decimal("3502049720")) is False
    assert _linea_plausible("No: POSE", Decimal("85701")) is False
    assert _linea_plausible(") ción", Decimal("18764116142437")) is False
    assert _linea_plausible("FILETE PECHUGA BUCANERO", Decimal("33854")) is True


def test_un_recibo_de_servicio_se_registra_como_un_solo_gasto(client):
    """Sin artículos, «registrar el gasto» usa el total detectado de la foto."""
    _, h = _registrar(client)
    cats = {c["nombre"]: c["id"] for c in client.get("/categorias", headers=h).json()}
    etqs = {e["nombre"]: e["id"] for e in client.get("/etiquetas", headers=h).json()}
    assert "Parqueadero" in etqs, "la etiqueta Parqueadero se siembra sola"

    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo(OCR_PARQUEADERO), "application/pdf")}
    ).json()
    detalle = client.post(f"/facturas/{f['id']}/lineas", headers=h, json={}).json()
    assert detalle["lineas"] == []
    assert detalle["tipo_documento"] == "parqueadero"

    r = client.post(
        f"/facturas/{f['id']}/confirmar-total",
        headers=h,
        json={"categoria_id": cats["Transporte"], "etiqueta_id": etqs["Parqueadero"]},
    )
    assert r.status_code == 200, r.text

    txs = client.get("/transacciones", headers=h).json()
    assert len(txs) == 1, txs
    assert float(txs[0]["monto"]) == 4100.0
    assert txs[0]["etiqueta_id"] == etqs["Parqueadero"]
