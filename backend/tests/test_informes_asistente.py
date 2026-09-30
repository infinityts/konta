"""Los informes a pedido: comparar meses, abrir una categoría y ver los artículos.

Lo que importa aquí es que las cuentas salgan del mismo sitio que las pantallas: si el asistente
dijera un total distinto al del panel, el usuario dejaría de creerle (y con razón).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import sessionmaker
from test_api import RECIBO, _registrar

from app import asistente
from app.models import Factura


def _gasto(client, h, monto: str, fecha: str, descripcion: str, categoria_id: str | None = None):
    r = client.post(
        "/transacciones",
        headers=h,
        json={
            "tipo": "gasto", "monto": monto, "fecha": fecha,
            "descripcion": descripcion, "categoria_id": categoria_id,
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _ingreso(client, h, monto: str, fecha: str, descripcion: str = "Salario"):
    r = client.post(
        "/transacciones", headers=h,
        json={"tipo": "ingreso", "monto": monto, "fecha": fecha, "descripcion": descripcion},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _categoria(client, h, nombre: str) -> str:
    return next(c["id"] for c in client.get("/categorias", headers=h).json() if c["nombre"] == nombre)


def _usuario(db, email: str):
    from app.models import Usuario

    return db.query(Usuario).filter(Usuario.email == email).one()


def test_comparar_dos_meses_con_cifras_conocidas(client, engine):
    _, h = _registrar(client, email="u@example.com")
    mercado = _categoria(client, h, "Mercado")
    _ingreso(client, h, "3000000", "2026-08-05")
    _gasto(client, h, "400000", "2026-08-10", "Mercado agosto", mercado)
    _ingreso(client, h, "3000000", "2026-09-05")
    _gasto(client, h, "500000", "2026-09-10", "Mercado septiembre", mercado)
    _gasto(client, h, "100000", "2026-09-12", "Gasolina")

    with sessionmaker(bind=engine).begin() as s:
        datos = asistente._comparar(s, _usuario(s, "u@example.com"), "2026-09", "2026-08")

    assert datos["totales"]["mes_a"]["gastos"] == 600000.0
    assert datos["totales"]["mes_b"]["gastos"] == 400000.0
    assert datos["totales"]["diferencia_gastos"] == 200000.0
    assert datos["totales"]["mes_a"]["balance"] == 2400000.0

    por_nombre = {c["categoria"]: c for c in datos["categorias"]}
    assert por_nombre["Mercado"]["diferencia"] == 100000.0
    assert por_nombre["Mercado"]["variacion_pct"] == 25.0
    # lo que más cambió va primero (Mercado +100.000 y «Sin categoría» +100.000 empatan: los dos
    # están arriba, y el orden entre iguales no se le exige a nadie)
    assert {c["categoria"] for c in datos["categorias"][:2]} == {"Mercado", "Sin categoría"}
    assert all(abs(c["diferencia"]) >= 100000.0 for c in datos["categorias"][:2])


def test_comparar_meses_donde_no_habia_nada(client, engine):
    _, h = _registrar(client, email="u@example.com")
    _gasto(client, h, "50000", "2026-09-10", "Algo")

    with sessionmaker(bind=engine).begin() as s:
        datos = asistente._comparar(s, _usuario(s, "u@example.com"), "2026-09", "2026-08")
    assert datos["totales"]["mes_b"]["gastos"] == 0.0
    assert datos["totales"]["diferencia_gastos"] == 50000.0
    # sin mes anterior no se puede dar porcentaje: se dice, no se inventa
    assert all(c["variacion_pct"] is None for c in datos["categorias"])


def test_el_detalle_de_una_categoria_la_abre_por_etiquetas(client, engine):
    _, h = _registrar(client, email="u@example.com")
    mercado = _categoria(client, h, "Mercado")
    etiquetas = client.get("/etiquetas", headers=h).json()
    lacteos = next((e for e in etiquetas if "Lácteos" in e["nombre"]), None)
    _gasto(client, h, "300000", "2026-09-10", "Mercado grande", mercado)
    if lacteos:
        client.post(
            "/transacciones",
            headers=h,
            json={
                "tipo": "gasto", "monto": "200000", "fecha": "2026-09-11",
                "descripcion": "Leche y queso", "categoria_id": mercado, "etiqueta_id": lacteos["id"],
            },
        )

    with sessionmaker(bind=engine).begin() as s:
        datos = asistente._detalle_de_categoria(s, _usuario(s, "u@example.com"), "mercado", "2026-09")

    assert datos["categoria"] == "mercado"
    assert datos["total"] == 500000.0
    assert len(datos["movimientos_mas_altos"]) == 2
    assert datos["movimientos_mas_altos"][0]["monto"] == 300000.0  # los más altos primero
    if lacteos:
        assert any("Lácteos" in e["etiqueta"] for e in datos["etiquetas"])


def test_el_detalle_avisa_si_esa_categoria_no_tiene_gastos(client, engine):
    _, h = _registrar(client, email="u@example.com")
    _gasto(client, h, "1000", "2026-09-10", "Algo")
    with sessionmaker(bind=engine).begin() as s:
        datos = asistente._detalle_de_categoria(s, _usuario(s, "u@example.com"), "Transporte", "2026-09")
    assert datos["nota"] == "No hay gastos de esa categoría en ese mes."
    assert datos["categorias_disponibles"], "y dice cuáles sí tienen gastos"


def test_los_productos_salen_del_detalle_de_las_facturas(client, engine):
    _, h = _registrar(client, email="u@example.com")
    # una factura de mercado con artículos, como las que sube el usuario
    with sessionmaker(bind=engine).begin() as s:
        usuario = _usuario(s, "u@example.com")
        factura = Factura(
            usuario_id=usuario.id,
            nombre_archivo="mercado.txt",
            texto_extraido=RECIBO,
            monto_detectado=Decimal("32416"),
            fecha_detectada=date(2026, 9, 20),
        )
        s.add(factura)
        s.flush()
        fid = str(factura.id)
    assert client.post(f"/facturas/{fid}/lineas", headers=h, json={}).status_code == 200

    with sessionmaker(bind=engine).begin() as s:
        datos = asistente._productos(s, _usuario(s, "u@example.com"), "2026-09")
    assert datos["mes"] == "2026-09"
    assert datos["productos"], "el detalle de la factura tiene que aparecer"
    primero = datos["productos"][0]
    assert {"descripcion", "total", "veces", "precio_promedio"} <= set(primero)


def test_el_asistente_recibe_las_mismas_cifras_que_el_panel(client, monkeypatch):
    """La prueba que sostiene la confianza: lo que ve el modelo es lo que dice la app."""
    _, h = _registrar(client, email="u@example.com")
    mercado = _categoria(client, h, "Mercado")
    _ingreso(client, h, "1000000", "2026-09-01")
    _gasto(client, h, "250000", "2026-09-10", "Mercado", mercado)

    panel = client.get("/reportes/panel?mes=2026-09", headers=h).json()

    vistos: list[list[dict]] = []

    def falso(mensajes, herramientas=None):
        vistos.append(mensajes)
        if len(vistos) == 1:
            from app.ia import ChatIa, LlamadaHerramienta

            return ChatIa(
                texto="",
                llamadas=[
                    LlamadaHerramienta(
                        id="c1", nombre="comparar", argumentos={"mes_a": "2026-09", "mes_b": "2026-08"}
                    )
                ],
                tokens_entrada=900, tokens_salida=50,
            )
        from app.ia import ChatIa

        return ChatIa(texto="En septiembre gastaste 250.000.", tokens_entrada=800, tokens_salida=60)

    from app import ia

    monkeypatch.setattr(ia, "chat", falso)
    r = client.post(
        "/asistente/preguntar",
        headers=h,
        json={"pregunta": "compárame septiembre con agosto"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["herramientas_usadas"] == ["comparar"]

    import json

    payload = json.loads(vistos[1][-1]["content"])
    assert payload["totales"]["mes_a"]["gastos"] == panel["kpis"]["gastos"]
    assert payload["totales"]["mes_a"]["ingresos"] == panel["kpis"]["ingresos"]
