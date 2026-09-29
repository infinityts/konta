"""Impuestos de una factura: lee el bloque tributario y lo concilia.

La factura electrónica de Cañaveral (y la mayoría en Colombia) trae un bloque así:

    Vta Gravada (*)....... 460,210 +
    Vta Exenta (**)....... 301,198 +
    Vta Excluida ....... 433,792 +
    Dscto Lista (D)....... 85,565 -
    Impuestos .......... 78,613 +
    IVA del 5% 5.00 42,959 2,148
    IVA del 19% 19.00 397,067 75,443
    ICO Bolsa 0.00 0 1,022

Aquí se extraen el descuento, las ventas gravada/exenta/excluida y **cada impuesto**
(IVA 5 %, IVA 19 %, ICO), y se **concilia** la suma del detalle contra el «Impuestos»
que declara el documento. Si no cuadra, `conciliado` es `False` y la UI puede avisar,
igual que hace la conciliación de los extractos.
"""

from __future__ import annotations

import re
from decimal import Decimal

from .dinero import buscar_montos, detectar_formato


def _ultimo_monto(linea: str, formato) -> Decimal | None:
    valores = buscar_montos(linea, formato)
    return valores[-1] if valores else None


def _parar_impuesto(linea: str, formato) -> dict | None:
    """`IVA del 19% 19.00 397,067 75,443` → nombre, tarifa, base y valor."""
    valores = buscar_montos(linea, formato)
    if len(valores) < 2:
        return None
    # Los últimos tres números son, en orden: tarifa, base, valor.
    valor = valores[-1]
    base = valores[-2]
    tarifa = valores[-3] if len(valores) >= 3 else Decimal("0")
    nombre = "IVA" if re.search(r"(?i)^iva", linea) else "ICO"
    return {"nombre": nombre, "tarifa": tarifa, "base": base, "valor": valor}


def detectar_impuestos(texto: str) -> dict | None:
    """Devuelve el bloque tributario de la factura, o `None` si no hay uno legible.

    Claves: `descuento`, `gravada`, `exenta`, `excluida` (ventas), `impuestos_total`,
    `detalle` (lista con `nombre`, `tarifa`, `base`, `valor`) y `conciliado` (si la
    suma del detalle coincide con `impuestos_total`).
    """
    formato = detectar_formato(texto.splitlines())
    resultado: dict = {
        "descuento": None,
        "gravada": None,
        "exenta": None,
        "excluida": None,
        "impuestos_total": None,
        "detalle": [],
    }

    for cruda in texto.splitlines():
        linea = cruda.strip()
        if not linea:
            continue

        # El descuento es la única línea que resta
        if re.search(r"(?i)\bdscto\b|descuento", linea) and linea.rstrip().endswith("-"):
            resultado["descuento"] = _ultimo_monto(linea, formato)
            continue

        # Ventas gravada / exenta / excluida
        for clave, patron in (
            ("gravada", r"\bgravada\b"),
            ("exenta", r"\bexenta\b"),
            ("excluida", r"\bexcluida\b"),
        ):
            if re.search(patron, linea, re.IGNORECASE):
                resultado[clave] = _ultimo_monto(linea, formato)

        # El total de impuestos que declara el documento
        if re.search(r"(?i)^impuestos", linea):
            resultado["impuestos_total"] = _ultimo_monto(linea, formato)

        # Cada impuesto: «IVA del 19% …» o «ICO Bolsa …»
        if re.search(r"(?i)^(iva|ico)\b", linea):
            detalle = _parar_impuesto(linea, formato)
            if detalle:
                resultado["detalle"].append(detalle)

    if not resultado["detalle"]:
        return None

    suma = sum((d["valor"] for d in resultado["detalle"]), Decimal("0"))
    resultado["conciliado"] = (
        resultado["impuestos_total"] is not None and suma == resultado["impuestos_total"]
    )
    return resultado


def a_json(impuestos: dict) -> dict:
    """Copia JSON-serializable (los `Decimal` pasan a texto) para `impuestos_detalle`."""
    def conv(valor):
        if isinstance(valor, Decimal):
            return str(valor)
        if isinstance(valor, dict):
            return {k: conv(v) for k, v in valor.items()}
        if isinstance(valor, list):
            return [conv(v) for v in valor]
        return valor

    return conv(impuestos)
