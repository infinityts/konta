"""El panel de Reportes devuelve todo en una llamada (KPIs, serie, categorías, mercado, IVA)."""

from __future__ import annotations

from test_api import _pdf_minimo, _registrar
from test_impuestos import FACTURA

from app.recurrencia import hoy


def _factura_del_mes() -> str:
    """La factura de ejemplo, con la fecha **de este mes**.

    La constante `FACTURA` trae una fecha fija (2026/9/16). El panel informa del **mes en curso**, así
    que con una fecha fija este test fallaba el día 1 de cada mes: pasó, y por eso ahora se calcula.
    """
    return FACTURA.replace("2026/9/16", f"{hoy():%Y/%-m/%-d}")


def test_panel_devuelve_todo(client):
    _, h = _registrar(client)
    factura = _factura_del_mes()
    f = client.post(
        "/facturas", headers=h, files={"archivo": ("f.pdf", _pdf_minimo(factura), "application/pdf")}
    ).json()
    client.post(f"/facturas/{f['id']}/lineas", headers=h, json={"texto": factura})
    client.post(f"/facturas/{f['id']}/confirmar-total", headers=h, json={})  # una compra

    cats = {c["nombre"]: c["id"] for c in client.get("/categorias", headers=h).json()}
    client.post(
        "/transacciones",
        headers=h,
        json={"tipo": "gasto", "monto": "50000", "fecha": str(hoy()),
              "descripcion": "otro mercado", "categoria_id": cats["Mercado"]},
    )

    r = client.get("/reportes/panel", headers=h)
    assert r.status_code == 200, r.text
    d = r.json()

    assert set(d["kpis"]) >= {"ingresos", "gastos", "balance", "iva", "compras"}
    assert len(d["serie"]) == 12
    assert d["impuestos"]["mes"] > 0, "la factura trae IVA"
    assert d["mercado"]["etiquetas"], "el detalle agrupa por etiqueta"
    assert d["mercado"]["productos"], "hay artículos"
    assert any(c["categoria"] == "Mercado" for c in d["categorias"])
