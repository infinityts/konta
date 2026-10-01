"""El asistente tiene que poder responder **cualquier** pregunta sobre la app.

Dos caminos, y cada pantalla necesita al menos uno:

- **cómo se hace** → un tema del manual (el asistente lo explica paso a paso).
- **mis datos** → una herramienta (el asistente consulta lo mismo que enseña la pantalla).

Este test es el que impide que vuelva a pasar lo de las transferencias entre cuentas: la app sabía
hacerlo, el manual no lo explicaba y el asistente —con razón— decía que no tenía ese tema. La lista
de pantallas se lee del código de la pantalla, no se copia a mano: si mañana se añade una pantalla y
nadie le pone tema ni herramienta, esto falla.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app import manual
from app.asistente import HERRAMIENTAS

PAGINAS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"

# Cada pantalla: o un tema del manual, o una herramienta, o el motivo de la excepción.
# `login`/`register` no son de la app por dentro; `informe` es del dueño (costes), no del cliente.
COBERTURA: dict[str, tuple[str, str, str]] = {
    # pantalla: (tema del manual o "", herramienta o "", motivo de la excepción o "")
    "Dashboard": ("ver cómo voy este mes", "resumen", ""),
    "Transacciones": ("registrar un gasto o un ingreso", "movimientos", ""),
    "Cuentas": ("crear una cuenta y poner su saldo inicial", "cuentas", ""),
    "Tarjetas": ("mirar mis tarjetas y lo que debo", "tarjetas", ""),
    "Presupuestos": ("hacer un presupuesto", "presupuestos", ""),
    "Metas": ("poner una meta de ahorro", "metas", ""),
    "Polizas": ("controlar los seguros y sus vencimientos", "polizas", ""),
    "Suscripciones": ("agregar un gasto que se repite", "recurrentes", ""),
    "IngresosRecurrentes": ("registrar un ingreso que se repite", "recurrentes", ""),
    "FlujoCaja": ("saber si me alcanza para lo que viene", "flujo", ""),
    "Reportes": ("ver en qué se me va la plata", "evolucion", ""),
    "Categorias": ("organizar con categorías y etiquetas", "detalle_de_categoria", ""),
    "Etiquetas": ("organizar con categorías y etiquetas", "movimientos", ""),
    "Facturas": ("subir una factura o un recibo", "facturas", ""),
    "ReglasOcr": ("arreglar una lectura que salió mal", "", ""),
    "Extractos": ("importar movimientos de un extracto", "", ""),
    "ValorExtractos": ("importar movimientos de un extracto", "", ""),
    "Importar": ("importar movimientos de un extracto", "", ""),
    "Mercado": ("usar la lista del mercado y los productos", "productos", ""),
    "Monedas": ("cambiar la moneda o ver la tasa del dólar", "", ""),
    "Notificaciones": ("configurar los avisos", "", ""),
    "Respaldo": ("exportar o respaldar mis datos", "", ""),
    "Planes": ("cambiar de plan o comprar lecturas", "mi_plan", ""),
    "Asistente": ("preguntarle al asistente", "ayuda", ""),
    "Login": ("", "", "no es una pantalla de la app por dentro"),
    "Register": ("", "", "no es una pantalla de la app por dentro"),
    "Informe": ("", "", "es del dueño (costes y márgenes), no del cliente"),
}


def _pantallas() -> list[str]:
    if not PAGINAS.is_dir():
        pytest.skip("no está el código de la pantalla (se prueba en el repositorio completo)")
    return sorted(p.stem for p in PAGINAS.glob("*.tsx"))


def test_ninguna_pantalla_se_queda_sin_explicacion():
    """Si se añade una pantalla y nadie la cubre, esto falla."""
    sin_cubrir = [p for p in _pantallas() if p not in COBERTURA]
    assert not sin_cubrir, (
        f"estas pantallas no están cubiertas por el asistente: {sin_cubrir}. "
        "Añade su tema al manual, o su herramienta, o el motivo de la excepción."
    )


def test_cada_pantalla_tiene_camino_para_preguntar():
    """Y lo que promete la tabla tiene que existir de verdad (no vale un nombre inventado)."""
    temas = manual.temas()
    herramientas = {h["function"]["name"] for h in HERRAMIENTAS}
    problemas = []
    for pantalla in _pantallas():
        tema, herramienta, exenta = COBERTURA.get(pantalla, ("", "", ""))
        if exenta:
            continue
        if tema and tema not in temas:
            problemas.append(f"{pantalla}: el tema «{tema}» no está en el manual")
        if herramienta and herramienta not in herramientas:
            problemas.append(f"{pantalla}: la herramienta «{herramienta}» no existe")
        if not tema and not herramienta:
            problemas.append(f"{pantalla}: ni tema ni herramienta ni motivo")
    assert not problemas, problemas


def test_el_asistente_sabe_de_las_cosas_que_se_preguntan_de_verdad():
    """Los temas imprescindibles, por nombre, para que no se caigan sin que nadie se entere."""
    temas = manual.temas()
    for imprescindible in (
        "transferir dinero entre mis cuentas",
        "crear una cuenta y poner su saldo inicial",
        "corregir o borrar un movimiento",
        "el IVA de mis facturas",
        "poner una meta de ahorro",
        "controlar los seguros y sus vencimientos",
        "saber si me alcanza para lo que viene",
        "importar movimientos de un extracto",
    ):
        assert imprescindible in temas, f"falta el tema: {imprescindible}"


def test_las_herramientas_nuevas_contestan_sin_reventar(client, engine):
    """Metas, seguros, recurrentes y flujo: devuelven su forma y dicen de qué pantalla salen.

    Con un usuario sin datos tienen que decir «no hay nada», no fallar: es la diferencia entre «no
    tienes metas» (útil) y un error (inútil).
    """
    from sqlalchemy.orm import sessionmaker
    from test_api import _registrar

    from app.asistente import ejecutar
    from app.models import Usuario

    _registrar(client)
    with sessionmaker(bind=engine).begin() as s:
        usuario = s.query(Usuario).one()
        for nombre, clave, pantalla in (
            ("metas", "metas", "Metas"),
            ("polizas", "polizas", "Seguros"),
            ("recurrentes", "recurrentes", "Gastos recurrentes"),
            ("flujo", "flujo", "Flujo de caja"),
        ):
            salida = ejecutar(s, usuario, nombre, {})
            assert salida["pantalla"] == pantalla, salida
            assert clave in salida, f"{nombre} no devolvió «{clave}»: {salida}"
