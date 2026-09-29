"""Parseo de dinero: **un solo** parser para los formatos que aparecen de verdad.

Antes había tres copias (una en `facturas`, otra en `importacion`, otra en `lineas`) y
solo la de `lineas` entendía el formato colombiano. Las otras dos leían `44.900` como
**44,9**, descartaban en silencio `1.500.000` y perdían el signo de `44.900-`.

Lo que hay que soportar, visto en facturas y extractos reales:

| Caso | Ejemplo | Resultado |
|---|---|---|
| Colombiano | `$5.195.786,83` | 5195786.83 |
| Estadounidense | `956,315.00` | 956315.00 |
| Solo puntos | `1.500.000` | 1500000 |
| **Ambiguo** (`44.900`) | con formato CO | 44900 |
| Signo al final | `44.900-` | -44900 |
| Paréntesis | `(120.000)` | -120000 |
| Espacios internos | `$ 5.32 2 ,2 0` | 5322.20 |
| Valor duplicado | `$9.568,71$9.568,71` | 9568.71 |

El caso ambiguo (`1.234` puede ser mil doscientos treinta y cuatro o uno con veintitrés)
se resuelve con el **formato del documento**, que se infiere del resto de las cifras
(`detectar_formato`). Cuando ni eso alcanza, en los extractos manda la conciliación: se
leen las dos formas y se queda la que cuadre con los totales del propio extracto.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from enum import StrEnum


class Formato(StrEnum):
    """Convención de separadores del documento."""

    CO = "co"  # 1.234.567,89
    US = "us"  # 1,234,567.89


# Símbolos y espacios que no forman parte del número (incluye espacios duros y finos)
_RUIDO = re.compile(r"(?i)(?:cop|usd|us\s*d|eur|mxn|clp|pen|brl|gtq|ars|clp|\$|\s|\u00a0|\u202f|\u2009)")
_SOLO_NUMERO = re.compile(r"\d[\d.,]*")
# Un valor dentro de un texto: con su símbolo, su signo (delante o detrás) o paréntesis
TOKEN_MONTO = re.compile(r"\$?\s*[-+(]?\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?(?:\)|-)?")


def buscar_montos(texto: str, formato: Formato | None = None) -> list[Decimal]:
    """Todos los valores que aparecen en un texto, en orden.

    Es lo que necesita un extracto: una línea trae la etiqueta y el valor juntos
    (`+ Intereses corrientes $97.624,49`), y a veces varios valores seguidos.
    """
    valores: list[Decimal] = []
    for bruto in TOKEN_MONTO.findall(texto or ""):
        valor = parsear_monto(bruto, formato)
        if valor is not None:
            valores.append(valor)
    return valores


def buscar_monto(texto: str, formato: Formato | None = None) -> Decimal | None:
    """El primer valor del texto (o `None`)."""
    valores = buscar_montos(texto, formato)
    return valores[0] if valores else None


def quitar_duplicado(texto: str) -> str:
    """Quita repeticiones consecutivas: `US D US D`, `T.C. T.C.`, `9.568,719.568,71`.

    Los extractos llegan así cuando el PDF dibuja el mismo dato dos veces (una sombra,
    un duplicado de capa). La repetición puede ser de **una** palabra (`T.C. T.C.`) o
    de un **bloque** (`US D US D`), así que se buscan bloques repetidos de izquierda a
    derecha, no solo palabras iguales seguidas.
    """
    s = (texto or "").strip()
    mitad = len(s) // 2
    if len(s) >= 4 and len(s) % 2 == 0 and s[:mitad] == s[mitad:]:
        return s[:mitad]

    partes = s.split()
    salida: list[str] = []
    i, n = 0, len(partes)
    while i < n:
        for tam in range(1, (n - i) // 2 + 1):
            if partes[i : i + tam] == partes[i + tam : i + 2 * tam]:
                salida.extend(partes[i : i + tam])
                i += 2 * tam
                break
        else:
            salida.append(partes[i])
            i += 1
    return " ".join(salida)


def _limpiar(texto: str) -> str:
    s = quitar_duplicado(texto or "")
    s = _RUIDO.sub("", s)
    return quitar_duplicado(s)


def parsear_monto(texto: str | None, formato: Formato | None = None) -> Decimal | None:
    """Devuelve el valor de `texto`, o `None` si no es un número válido.

    `formato` solo hace falta para los casos ambiguos (`44.900`, `1,234`); si no se
    indica, se asume el colombiano, que es lo correcto para esta app.
    """
    s = _limpiar(texto or "")
    if not s:
        return None

    negativo = False
    if s.startswith("-"):
        negativo, s = True, s[1:]
    elif s.endswith("-"):
        negativo, s = True, s[:-1]
    elif s.startswith("(") and s.endswith(")"):
        negativo, s = True, s[1:-1]
    s = s.strip("()")

    if not _SOLO_NUMERO.fullmatch(s):
        return None

    if "." in s and "," in s:
        # El último separador es el decimal; el otro es de miles
        decimal = "." if s.rfind(".") > s.rfind(",") else ","
        miles = "," if decimal == "." else "."
        s = s.replace(miles, "").replace(decimal, ".")
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        partes = s.split(sep)
        if len(partes) > 2:
            # Varios separadores iguales: son de miles (1.500.000 / 1,500,000)
            if not all(len(p) == 3 for p in partes[1:]):
                return None
            s = "".join(partes)
        else:
            entera, decimales = partes
            if len(decimales) == 3:
                # Ambiguo: `44.900` es 44900 en CO y 44,9 en US
                convencion = formato or Formato.CO
                usa_miles = (convencion == Formato.CO and sep == ".") or (
                    convencion == Formato.US and sep == ","
                )
                s = entera + decimales if usa_miles else f"{entera}.{decimales}"
            elif len(decimales) in (1, 2):
                s = f"{entera}.{decimales}"
            else:
                return None

    try:
        valor = Decimal(s)
    except InvalidOperation:
        return None
    return -valor if negativo else valor


def detectar_formato(textos: Iterable[str]) -> Formato:
    """Infiere la convención de separadores del documento.

    Solo cuentan las cifras que **delatan** el formato: las que llevan los dos
    separadores (el orden lo dice todo), las que tienen 1 o 2 decimales tras el
    separador, y las que agrupan de tres en tres después de una coma (`24,674`), que en
    un documento con muchas así solo pueden ser miles. Las ambiguas (`1.234`) no aportan:
    las decide el formato del conjunto.
    """
    puntos_co = puntos_us = 0
    for texto in textos:
        for bruto in _SOLO_NUMERO.findall(texto or ""):
            s = bruto.rstrip(".,")
            if "." in s and "," in s:
                if s.rfind(",") > s.rfind("."):
                    puntos_co += 2
                else:
                    puntos_us += 2
            elif s.count(".") == 1 and "," not in s and len(s.split(".")[1]) in (1, 2):
                puntos_us += 1
            elif s.count(",") == 1 and "." not in s and len(s.split(",")[1]) in (1, 2):
                puntos_co += 1
            elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", s):
                # Coma seguida de grupos de exactamente 3 dígitos: es separador de miles
                # (`24,674` = 24674). Lo usan cajas registradoras colombianas que imprimen
                # el dinero al estilo de EE. UU. en vez del `24.674` de siempre.
                puntos_us += 1
    return Formato.CO if puntos_co >= puntos_us else Formato.US
