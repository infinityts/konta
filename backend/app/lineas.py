"""Parser de líneas de un recibo colombiano (D1, Ara, Éxito, Olímpica, gasolina…).

Convierte el texto del OCR en artículos. Los recibos usan dos formatos:

    # Dos líneas (el más común en D1 / Ara)
    PECHUGA POLLO BANDEJA
    1.234 KG X 12.900            15.916

    # Una sola línea
    ARROZ DIANA 500G 2 UN X 2.500       5.000

Ojo con el formato numérico colombiano: **el punto separa miles** (`15.916` son
quince mil novecientos dieciséis) y la **coma es decimal** (`15,50`). La única
ambigüedad son las cantidades de peso (`1.234 KG`), que se resuelven por unidad.

Ignora todo lo que no es un artículo (totales, IVA, medios de pago, datos del
comercio) y detecta el **tipo de documento** para saber qué esperar.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from .dinero import Formato, parsear_monto

# Orden importa: las alternativas largas van primero (GALONES antes que G).
UNIDADES = r"(?:GALONES|GALON|GAL|KGS|KG|GRS|GR|LT|LTS|ML|UND|UNI|UN|PZ|DOC|BOLSA|PAQ|G|L)"

UNIDADES_PESO_VOLUMEN = ("KG", "KGS", "G", "GR", "GRS", "LT", "LTS", "L", "ML", "GAL", "GALON", "GALONES")

# Si la línea contiene alguna de estas, NO es un artículo.
IGNORAR = (
    "TOTAL", "SUBTOTAL", "IVA", "IMPUESTO", "PROPINA", "CAMBIO", "EFECTIVO",
    "TARJETA", "DEBITO", "CREDITO", "DEVOLUCION", "BASE GRAVABLE", "BASE",
    "ARTICULOS", "GRACIAS", "NIT", "RESOLUCION", "FACTURA", "CAJA", "CAJERO",
    "FECHA", "HORA", "VENDEDOR", "CLIENTE", "AUTORIZADO", "PUNTOS", "AHORRO",
    "REDENCION", "REGIMEN", "TELEFONO", "DIRECCION", "SUCURSAL", "DESCUENTO",
    "VUELTAS", "RECIBIDO", "COTIZACION", "PEDIDO", "MESA", "DOMICILIO",
    "CUF", "CUFE", "AUTORIZACION", "VENCE", "WWW", "HTTP",
)

# "2 UN X 2.500" / "1.234 KG X 12.900" / "3 x 4.000"
PATRON_CANT_X_UNIT = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*({UNIDADES})?\s*[Xx*]\s*\$?\s*(\d[\d.,]*)"
)

# Dinero: 1.234.567 · 12.900 · 4500. Se excluye lo que va seguido de unidad (500G)
PATRON_MONTO = re.compile(rf"\$?\s*(\d{{1,3}}(?:[.,]\d{{3}})+|\d{{3,}})(?!\s*{UNIDADES}(?![A-Z]))")

LETRAS = re.compile(r"[A-ZÑ]{3,}")


def sin_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _decimal(s: str) -> Decimal | None:
    s = s.strip().replace("$", "").replace(" ", "")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def monto(s: str) -> Decimal | None:
    """Dinero de un recibo: formato colombiano (delega en `dinero.parsear_monto`)."""
    return parsear_monto(s, Formato.CO)


def cantidad(s: str, unidad: str | None) -> Decimal | None:
    """Cantidad: `1.234 KG` son 1,234 kg, pero `1.500 G` son 1.500 gramos."""
    s = s.strip().replace(" ", "")
    if "," in s:
        return _decimal(s.replace(".", "").replace(",", "."))
    if "." in s:
        u = (unidad or "").upper()
        # Con peso/volumen el punto es decimal; con unidades cuenta, es de miles
        return _decimal(s) if u in UNIDADES_PESO_VOLUMEN else _decimal(s.replace(".", ""))
    return _decimal(s)


def _limpiar_descripcion(texto: str) -> str:
    t = re.sub(r"[\$@|_=~]+", " ", texto)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" .-*:").strip()


def _es_articulo(texto: str) -> bool:
    return bool(LETRAS.search(sin_acentos(texto).upper()))


def parsear_lineas(texto: str) -> list[dict]:
    """Devuelve los artículos detectados, en orden.

    Cada artículo: {descripcion, cantidad, valor_unitario, valor_total}
    """
    articulos: list[dict] = []
    pendiente = ""  # descripción sin monto (formato de dos líneas)

    for cruda in texto.splitlines():
        t = cruda.strip()
        if len(t) < 3:
            continue
        if any(p in sin_acentos(t).upper() for p in IGNORAR):
            pendiente = ""
            continue

        cant = unit = None
        m = PATRON_CANT_X_UNIT.search(t)
        if m:
            cant = cantidad(m.group(1), m.group(2))
            unit = monto(m.group(3))
            descripcion = t[: m.start()]
            resto = t[m.end() :]
            coincidencias = list(PATRON_MONTO.finditer(resto))
            if not coincidencias:
                # La línea solo trae "cant x unit" (el total es el unitario)
                total = unit
            else:
                total = monto(coincidencias[-1].group(1))
        else:
            coincidencias = list(PATRON_MONTO.finditer(t))
            if not coincidencias:
                # Sin valor: puede ser la descripción de la línea siguiente
                solo_texto = _limpiar_descripcion(t)
                if _es_articulo(solo_texto):
                    pendiente = solo_texto
                continue
            total = monto(coincidencias[-1].group(1))
            descripcion = t[: coincidencias[-1].start()]

        if total is None or total <= 0:
            pendiente = ""
            continue

        texto_desc = _limpiar_descripcion(descripcion)
        # Si la línea era solo un número, la descripción viene de la anterior
        if not _es_articulo(texto_desc) and pendiente:
            texto_desc = pendiente
        pendiente = ""

        if not _es_articulo(texto_desc):
            continue

        articulos.append(
            {
                "descripcion": texto_desc[:200],
                "cantidad": cant,
                "valor_unitario": unit,
                "valor_total": total,
            }
        )

    return articulos


# --------------------------------------------------------------------------- #
# Tipo de documento
# --------------------------------------------------------------------------- #

CLAVES_TIPO: list[tuple[str, tuple[str, ...]]] = [
    ("gasolina", ("GASOLINA", "COMBUSTIBLE", "DIESEL", "TERPEL", "PRIMAX", "TEXACO", "EDS ", "GALONES", "BIODIESEL")),
    ("servicios", ("ENERGIA", "ELECTRICIDAD", "ACUEDUCTO", "ALCANTARILLADO", "GAS NATURAL", "EPM", "ENEL", "CODENSA", "VANTI", "ETB", "CLARO", "MOVISTAR", "TIGO")),
    ("restaurante", ("RESTAURANTE", "CORRIENTAZO", "COCINA", "PARRILLA", "PIZZERIA", "CAFETERIA")),
    ("mercado", ("D1", "ARA", "EXITO", "OLIMPICA", "JUMBO", "CARULLA", "MAKRO", "MERCADO", "SUPERMERCADO", "ALMACEN", "TIENDA", "EURO", "JUSTO & BUENO", "LA 14")),
]


def detectar_tipo(texto: str, lineas: list[dict] | None = None) -> str:
    """Clasifica el documento: mercado, gasolina, servicios, restaurante u otro."""
    norm = sin_acentos(texto).upper()
    for tipo, claves in CLAVES_TIPO:
        if any(c in norm for c in claves):
            return tipo
    if lineas and len(lineas) >= 6:
        return "mercado"
    return "otro"
