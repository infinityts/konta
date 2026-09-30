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

from .dinero import Formato, detectar_formato, parsear_monto

# Orden importa: las alternativas largas van primero (GALONES antes que G).
UNIDADES = r"(?:GALONES|GALON|GAL|KGS|KG|GRS|GR|LT|LTS|ML|UND|UNI|UN|PZ|DOC|BOLSA|PAQ|G|L)"

UNIDADES_PESO_VOLUMEN = ("KG", "KGS", "G", "GR", "GRS", "LT", "LTS", "L", "ML", "GAL", "GALON", "GALONES")

# Si la línea contiene alguna de estas, NO es un artículo.
IGNORAR = (
    "TOTAL", "SUBTOTAL", "IVA", "IMPUESTO", "PROPINA", "EFECTIVO",
    "TARJETA", "DEBITO", "CREDITO", "DEVOLUCION", "BASE GRAVABLE", "BASE",
    "ARTICULOS", "GRACIAS", "NIT", "RESOLUCION", "FACTURA", "CAJA", "CAJERO",
    "FECHA", "HORA", "VENDEDOR", "CLIENTE", "AUTORIZADO", "PUNTOS", "AHORRO",
    "REDENCION", "REGIMEN", "TELEFONO", "DIRECCION", "SUCURSAL", "DESCUENTO",
    "VUELTAS", "RECIBIDO", "COTIZACION", "PEDIDO", "MESA", "DOMICILIO",
    "CUF", "CUFE", "AUTORIZACION", "VENCE", "WWW", "HTTP",
    # Cabeceras y pies típicos de un recibo **fotografiado** (parqueaderos, servicios)
    "AVENIDA", "CARRERA", "CALLE", "DIAGONAL", "TRANSVERSAL", "INGRESO",
    "MATRICULA", "DURACION", "OPERARIO", "METODO", "PREFIJO", "POLIZA",
    "SOFTWARE", "FABRICANTE", "CONSUMIDOR", "EQUIVALENTE", "DOCUMENTO",
    # Pie del recibo que el OCR convirtió en «artículos» con valores absurdos:
    # «SE Rango desde 85550» ($85.550) y «Hasta 500000» ($500.000)
    "RANGO", "DESDE", "HASTA", "VIGENCIA", "VIGENTE",
)

# Se busca por **palabra completa**, no por subcadena: con `in`, `PARMESANO` contenía
# `MESA` y el queso parmesano se caía de la factura como si fuera una línea de restaurante.
IGNORAR_RE = re.compile(r"\b(?:" + "|".join(re.escape(p) for p in IGNORAR) + r")\b")

# Palabras que solo descartan la línea si son **la etiqueta** (van al principio). «Cambio» en
# medio de una descripción es legítimo: «Cuota de garantía del tipo de cambio» es una comisión
# que sí se pagó, y con la palabra en la lista general se la comía.
# Renglones que **no** son artículos: datos del documento (NIT, cajero, resolución) o totales
# que la app ya lee aparte (subtotal, IVA, propina). Se comparan como **prefijo** de la línea,
# así que solo van aquí palabras que no pueden empezar el nombre de un producto.
IGNORAR_ETIQUETA = (
    "CAMBIO", "VUELTAS",
    "NIT", "CEDULA", "CAJERO", "TERMINAL", "POS", "AUTORIZACION", "RESOLUCION",
    "FACTURA No", "FACTURA N", "No FACTURA", "SUBTOTAL", "IVA", "IMPUESTO",
    "BASE GRAVABLE", "DESCUENTO", "PROPINA", "REDONDEO", "EFECTIVO",
    "TOTAL", "VALOR A PAGAR", "VALOR TOTAL", "MONTO", "FECHA", "HORA",
    "CLIENTE", "VENDEDOR", "GRACIAS",
)
IGNORAR_ETIQUETA_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(p) for p in IGNORAR_ETIQUETA) + r")\b"
)

# Una tasa de cambio no es un artículo: «1 USD = 3370.42 COP», «Tasa de cambio».
TASA_RE = re.compile(r"(?i)\bTASA\s+DE\s+CAMBIO\b|\b(?:USD|EUR)\s*=|= \s*[\d.,]+\s*(?:COP|USD|EUR)\b")

# "2 UN X 2.500" / "1.234 KG X 12.900" / "3 x 4.000"
PATRON_CANT_X_UNIT = re.compile(
    rf"(\d+(?:[.,]\d+)?)\s*({UNIDADES})?\s*[Xx*]\s*\$?\s*(\d[\d.,]*)"
)

# Dinero: 1.234.567 · 12.900 · 4500. Se excluye lo que va seguido de unidad (500G)
# Dinero: 1.234.567 · 12.900 · 4500 · **y con centavos** (1.234,56 / 87,630.92). Antes el
# patrón paraba en el grupo de miles y se comía los decimales: un pedido de Amazon en pesos
# «87,630.92» se leía como 87.630 y la suma no cuadraba con el total. Se excluye lo que va
# seguido de unidad (500G) y los números de una o dos cifras (cantidades, no precios).
PATRON_MONTO = re.compile(
    rf"\$?\s*(\d{{1,3}}(?:[.,]\d{{3}})+(?:[.,]\d{{2}})?|\d{{3,}}(?:[.,]\d{{2}})?)"
    rf"(?!\s*{UNIDADES}(?![A-Z]))"
)

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


def monto(s: str, formato: Formato = Formato.CO) -> Decimal | None:
    """Dinero de un recibo, en el formato del documento (`dinero.parsear_monto`).

    El formato importa: hay cajas registradoras colombianas que imprimen `24,674`
    (veinticuatro mil seiscientos setenta y cuatro) en vez de `24.674`.
    """
    return parsear_monto(s, formato)


def cantidad(s: str, unidad: str | None) -> Decimal | None:
    """Cantidad: `1.234 KG` son 1,234 kg, pero `1.500 G` son 1.500 gramos."""
    s = s.strip().replace(" ", "")
    if "," in s:
        return _decimal(s.replace(".", "").replace(",", "."))
    if "." in s:
        u = (unidad or "").upper()
        # Dos decimales tras el punto son decimales siempre: `4.00 un` son 4 unidades
        # (antes se leían como 400, porque con «unidad de cuenta» el punto se tomaba de
        # miles). Con tres dígitos manda la unidad: en peso/volumen es decimal.
        if len(s.split(".")[-1]) != 3:
            return _decimal(s)
        return _decimal(s) if u in UNIDADES_PESO_VOLUMEN else _decimal(s.replace(".", ""))
    return _decimal(s)


def _limpiar_descripcion(texto: str) -> str:
    t = re.sub(r"[\$@|_=~]+", " ", texto)
    # El código de la moneda no es parte del nombre del artículo: «Productos: COP» -> «Productos»
    t = re.sub(r"(?i)\b(?:COP|USD|EUR|MXN|PEN|CLP|ARS)\b", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip(" .-*:").strip()


def _es_articulo(texto: str) -> bool:
    return bool(LETRAS.search(sin_acentos(texto).upper()))


# --------------------------------------------------------------------------- #
# Facturas con un artículo por línea y su línea de valores
# --------------------------------------------------------------------------- #

ENCABEZADO_TABLA = re.compile(r"(?i)item\s+descripcion|referencia\s+cant")
# `12 YOGURT VITAD*150g FRESA`
PATRON_ITEM_NUMERADO = re.compile(r"^\s*(\d{1,3})\s+(\S.{2,})$")
# `023029 1.372 kg 24,674 33,854**`  /  `COVA-00 1.00 un 5,950 5,950*`
# Al final puede venir la marca del artículo: `*` gravado, `**` exento, `D` descuento
# (y combinaciones: `6,375* D`).
PATRON_VALORES = re.compile(
    rf"^\s*(?P<ref>\S+)\s+(?P<cant>\d+(?:[.,]\d+)?)\s+(?P<um>{UNIDADES})\s+"
    rf"(?P<vu>[\d.,]+)\s+(?P<total>[\d.,]+)(?P<marca>[\sD*]*)$",
    re.IGNORECASE,
)
FIN_TABLA = re.compile(r"(?i)^\s*[-\s]*T\s?O\s?T\s?A\s?L\b")


def _parsear_factura_numerada(texto: str, formato: Formato) -> list[dict] | None:
    """Artículos de una factura con **una línea por artículo y otra de valores**.

       1 FILETE PECHUGA BUCANERO A GRANEL
       023029 1.372 kg 24,674 33,854**

    Se apoya en tres cosas que este formato cumple: los artículos están **numerados en
    orden** (1, 2, 3…), cada uno trae su línea de valores (aunque la referencia sea
    `COVA-00`, un código de promoción) y la tabla **termina** en el `T O T A L`. Antes
    esta factura se leía con el parser de recibos y se colaban en la lista el `Tel:`, el
    `TPV` y las líneas del pie, además de perder artículos.

    Devuelve `None` si el documento no es de este tipo (y entonces manda el otro parser).
    """
    lineas = texto.splitlines()
    desde = None
    for i, linea in enumerate(lineas):
        if ENCABEZADO_TABLA.search(linea):
            desde = i + 1
            break
    if desde is None:
        return None

    articulos: list[dict] = []
    esperado: int | None = None
    pendiente: str | None = None
    for linea in lineas[desde:]:
        t = linea.strip()
        if FIN_TABLA.match(t):
            break

        item = PATRON_ITEM_NUMERADO.match(t)
        if item and (esperado is None or int(item.group(1)) == esperado):
            numero = int(item.group(1))
            if esperado is None and numero > 3:
                return None  # no empieza cerca del 1: no es una tabla de artículos
            esperado = numero + 1
            pendiente = _limpiar_descripcion(item.group(2).rstrip("*"))
            continue

        valores = PATRON_VALORES.match(t)
        if valores and pendiente:
            total = monto(valores.group("total"), formato)
            if total is not None and total > 0 and _es_articulo(pendiente):
                estrellas = (valores.group("marca") or "").count("*")
                iva_tipo = "exento" if estrellas >= 2 else "gravado" if estrellas == 1 else "excluido"
                articulos.append(
                    {
                        "descripcion": pendiente[:200],
                        "cantidad": cantidad(valores.group("cant"), valores.group("um")),
                        "valor_unitario": monto(valores.group("vu"), formato),
                        "valor_total": total,
                        "iva_tipo": iva_tipo,
                    }
                )
            pendiente = None
            continue

        # Ni artículo ni valores: puede ser la continuación del nombre (los largos se parten)
        if pendiente and not PATRON_MONTO.search(t):
            continuacion = _limpiar_descripcion(t)
            if _es_articulo(continuacion):
                pendiente = f"{pendiente} {continuacion}"[:200]

    return articulos if len(articulos) >= 3 else None


def _negativo(linea: str, corte: int) -> bool:
    """¿El importe que empieza en `corte` va con signo negativo?

    «Envio gratis de Prime: -COP 38.456,49»: el menos va **antes** del símbolo de la moneda,
    así que el patrón del monto no lo ve. Sin esto, un descuento se sumaba como un cobro y el
    detalle no cuadraba con el total.
    """
    return bool(re.search(r"-\s*(?:COP|USD|EUR|\$)?\s*$", linea[:corte].rstrip()))


def _linea_plausible(descripcion: str, total: Decimal | None) -> bool:
    """Descarta el ruido típico de una **foto**: NIT, direcciones, correos, resoluciones.

    El OCR de una foto mete la cabecera y el pie del recibo (NIT, dirección, teléfono,
    número de resolución). Sin este filtro, un recibo de parqueadero produce seis
    «artículos» que en realidad son la cabecera.
    """
    d = (descripcion or "").strip()
    # Un artículo tiene nombre: «Eta» o «asta» son trozos de la cabecera
    if len(d) < 5 or sum(1 for c in d if c.isalpha()) < 4:
        return False
    bajo = sin_acentos(d).lower()
    if "@" in d or ".com" in bajo or "www" in bajo:
        return False
    letras = sum(1 for c in d if c.isalpha())
    if letras < len(d) * 0.4:
        return False
    # Etiquetas de documento («No: POSE-85701», «Ref. 123»), no productos
    primera = re.split(r"[\s:.\-]+", bajo)[0] if bajo else ""
    if primera in {
        "no", "n", "num", "nro", "numero", "doc", "documento", "consec",
        "consecutivo", "ref", "referencia", "cude", "cufe", "pose", "radicado",
    }:
        return False
    # Un número de resolución (18.764.116.142.437) no es un precio
    return not (total is not None and total > Decimal("50000000"))


def parsear_lineas(texto: str, formato: Formato | None = None) -> list[dict]:
    """Devuelve los artículos detectados, en orden.

    Cada artículo: {descripcion, cantidad, valor_unitario, valor_total}

    Primero se prueba el formato de **factura numerada** (una línea por artículo y su
    línea de valores), que es el de las cajas grandes; si no, el de recibo de siempre.
    """
    formato = formato or detectar_formato(texto.splitlines())
    de_factura = _parsear_factura_numerada(texto, formato)
    if de_factura is not None:
        return de_factura

    articulos: list[dict] = []
    pendiente = ""  # descripción sin monto (formato de dos líneas)

    for cruda in texto.splitlines():
        t = cruda.strip()
        if len(t) < 3:
            continue
        plano = sin_acentos(t).upper()
        # `**** 0571` es una cuenta enmascarada, no un artículo de 571
        if "****" in t or "····" in t:
            pendiente = ""
            continue
        if IGNORAR_RE.search(plano) or IGNORAR_ETIQUETA_RE.match(plano) or TASA_RE.search(t):
            pendiente = ""
            continue

        cant = unit = None
        m = PATRON_CANT_X_UNIT.search(t)
        if m:
            cant = cantidad(m.group(1), m.group(2))
            unit = monto(m.group(3), formato)
            descripcion = t[: m.start()]
            resto = t[m.end() :]
            coincidencias = list(PATRON_MONTO.finditer(resto))
            if not coincidencias:
                # La línea solo trae "cant x unit" (el total es el unitario)
                total = unit
            else:
                total = monto(coincidencias[-1].group(1), formato)
                if total is not None and _negativo(t, m.end() + coincidencias[-1].start()):
                    total = -total
        else:
            coincidencias = list(PATRON_MONTO.finditer(t))
            if not coincidencias:
                # Sin valor: puede ser la descripción de la línea siguiente
                solo_texto = _limpiar_descripcion(t)
                if _es_articulo(solo_texto):
                    pendiente = solo_texto
                continue
            total = monto(coincidencias[-1].group(1), formato)
            if total is not None and _negativo(t, coincidencias[-1].start()):
                total = -total
            descripcion = t[: coincidencias[-1].start()]

        # Un descuento viene en negativo (`-COP 38.456,49`) y **sí** es una línea: se
        # descuenta del total. Solo se descarta el cero.
        if total is None or total == 0:
            pendiente = ""
            continue

        texto_desc = _limpiar_descripcion(descripcion)
        # Si la línea era solo un número, la descripción viene de la anterior
        if not _es_articulo(texto_desc) and pendiente:
            texto_desc = pendiente
        pendiente = ""

        if not _es_articulo(texto_desc) or not _linea_plausible(texto_desc, total):
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
    # El parqueadero va primero: su recibo trae «PARKING» en el pie y, si no, el
    # heurístico de «muchas líneas» lo tomaría por un mercado.
    ("parqueadero", ("PARKING", "PARQUEADERO", "ESTACIONAMIENTO", "MATRICULA:", "DURACION:")),
    ("gasolina", ("GASOLINA", "COMBUSTIBLE", "DIESEL", "TERPEL", "PRIMAX", "TEXACO", "EDS ", "GALONES", "BIODIESEL")),
    ("servicios", (
        "ENERGIA", "ELECTRICIDAD", "ACUEDUCTO", "ALCANTARILLADO", "GAS NATURAL", "EPM",
        "ENEL", "CODENSA", "VANTI", "ETB", "CLARO", "MOVISTAR", "TIGO",
        # Comprobantes de **pago** de un servicio (PSE o pasarela): traen el comprobante y el
        # «Valor del Pago», no artículos. Sin esto, el pago de EMCALI se tomaba por mercado.
        "EMCALI", "SERVICIOS PUBLICOS", "PAGO PSE", "TRANSACCION APROBADA",
        "CONSECUTIVO COMERCIO", "NUMERO DE COMPROBANTE", "COMPROBANTE EN LINEA",
        # Confirmaciones de pago («¡Pago realizado con éxito!», «Detalles del pago»): traen
        # etiquetas y valores, no artículos. Sin esto se tomaban por mercado y el «Monto»
        # acababa siendo un artículo.
        "PAGO REALIZADO CON EXITO", "DETALLES DEL PAGO", "PAGO DE FACTURA",
        "REFERENCIA DE PAGO", "ESTADO TRANSACCION", "GASES DE OCCIDENTE",
    )),
    ("restaurante", ("RESTAURANTE", "CORRIENTAZO", "COCINA", "PARRILLA", "PIZZERIA", "CAFETERIA")),
    ("mercado", ("D1", "ARA", "EXITO", "OLIMPICA", "JUMBO", "CARULLA", "MAKRO", "MERCADO", "SUPERMERCADO", "ALMACEN", "TIENDA", "EURO", "JUSTO & BUENO", "LA 14")),
]


def detectar_tipo(texto: str, lineas: list[dict] | None = None) -> str:
    """Clasifica el documento: parqueadero, gasolina, servicios, restaurante, mercado u otro."""
    norm = sin_acentos(texto).upper()
    for tipo, claves in CLAVES_TIPO:
        if any(c in norm for c in claves):
            return tipo
    if lineas and len(lineas) >= 6:
        return "mercado"
    return "otro"
