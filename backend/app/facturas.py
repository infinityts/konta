"""Extracción de datos de facturas y recibos.

1. PDF digital  -> texto con `pypdf`.
2. PDF escaneado o **foto** (JPG/PNG) -> OCR con `pytesseract`.
   Las fotos pasan por un preprocesado (grises, autocontraste, reescalado y
   binarizado) porque Tesseract falla con fotos de recibos arrugados.
3. Heurísticas para detectar monto, fecha y **las líneas de artículos**
   (ver `lineas.py`).

Requiere los binarios `tesseract-ocr` (con el paquete de español) y
`poppler-utils` (solo para el OCR de PDF).
"""

from __future__ import annotations

import io
import os
import re
from datetime import date
from decimal import Decimal

from .dinero import detectar_formato, parsear_monto

TIPOS_IMAGEN = ("image/jpeg", "image/jpg", "image/png", "image/webp")
EXTENSIONES_IMAGEN = (".jpg", ".jpeg", ".png", ".webp")


def es_imagen(nombre: str, content_type: str | None = None) -> bool:
    if content_type and content_type.split(";")[0].strip().lower() in TIPOS_IMAGEN:
        return True
    return nombre.lower().endswith(EXTENSIONES_IMAGEN)


# Tesseract usa OpenMP y, sin límite, lanza más hilos de los que el servidor puede atender:
# se pelean entre ellos y una página pasaba de **42 s a 0,28 s** solo con esta línea (medido
# en el contenedor). Con el límite, leer un escaneado de 12 páginas es cuestión de segundos.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")


def _preprocesar(imagen):
    """Mejora la legibilidad de una foto de recibo antes del OCR."""
    from PIL import Image, ImageFilter, ImageOps

    img = imagen.convert("L")  # escala de grises
    # Si la foto es pequeña, se agranda: Tesseract lee mejor a partir de ~1000 px
    if min(img.size) < 1000:
        factor = max(1, 1000 // max(1, min(img.size)))
        img = img.resize((img.width * factor, img.height * factor), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = img.filter(ImageFilter.SHARPEN)
    # Binarizado adaptativo simple: el umbral a la media ayuda con sombras
    return img.point(lambda p: 255 if p > 140 else 0)


# Modo de segmentación del OCR: **una sola columna de texto**.
#
# Con el automático, Tesseract detecta dos columnas en una confirmación de pago (etiqueta a la
# izquierda, valor a la derecha) y las lee **por separado**: primero todas las etiquetas y
# luego todos los valores, así que se pierde qué va con qué. Medido con una confirmación real:
# 24 líneas sueltas y ninguna con el valor junto a su texto; con `--psm 4`, 14 líneas y el
# «Monto: $46.477» en su sitio. En la foto de un recibo de parqueadero da lo mismo que antes.
PSM_COLUMNA_UNICA = "--psm 4"


def _ocr_imagen(imagen) -> str:
    import pytesseract

    return pytesseract.image_to_string(_preprocesar(imagen), lang="spa", config=PSM_COLUMNA_UNICA)


# Tope de páginas que se rasterizan para OCR (ver `extraer_texto`). El texto digital no
# tiene tope: es el caso de las facturas electrónicas y los extractos descargados del banco.
PAGINAS_OCR = 25


def extraer_texto(
    contenido: bytes,
    nombre: str = "",
    content_type: str | None = None,
    password: str | None = None,
) -> str:
    """Devuelve el texto de un PDF o de una foto de recibo.

    Los PDF de factura electrónica suelen venir **protegidos con contraseña** (el NIT del
    emisor es lo habitual). Si lo está y no hay contraseña —o no es la correcta— se
    **avisa** con un `ValueError`: devolver un texto vacío haría pensar que el archivo no se
    pudo leer, que es otra cosa.
    """
    if es_imagen(nombre, content_type):
        try:
            from PIL import Image

            return _ocr_imagen(Image.open(io.BytesIO(contenido)))
        except Exception:  # noqa: BLE001 — el OCR depende de binarios externos (tesseract/poppler): si fallan, se devuelve lo que se pudo extraer
            return ""

    # 1. PDF digital
    texto = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contenido))
        if reader.is_encrypted and not (password and reader.decrypt(password)):
            raise ValueError("El PDF está protegido y la contraseña no es correcta")
        # El modo `layout` respeta las **columnas**: en una factura o un comprobante de pago
        # la etiqueta y su valor quedan en la misma línea. Sin esto, un PDF de dos columnas
        # sale mezclado y el monto se acaba leyendo de un número de referencia.
        partes: list[str] = []
        for pagina in reader.pages:
            try:
                partes.append(pagina.extract_text(extraction_mode="layout") or "")
            except Exception:  # noqa: BLE001 — si el modo layout falla, sirve el normal
                partes.append(pagina.extract_text() or "")
        texto = "\n".join(partes)
    except ValueError:
        raise  # la contraseña es un dato de la subida, no un PDF raro
    except Exception:  # noqa: BLE001 — el OCR depende de binarios externos (tesseract/poppler): si fallan, se devuelve lo que se pudo extraer
        texto = ""

    if texto.strip():
        return texto

    # 2. PDF escaneado -> OCR
    #
    # Se rasteriza a **150 ppp** (el OCR de un documento de texto no gana nada con 200) y se
    # limita a las primeras páginas: un escaneado de 12 páginas a 200 ppp tarda más de un
    # minuto y la petición se caía por tiempo de espera. Un extracto o una factura caben de
    # sobra en ese tope; el texto **digital** (el caso normal) no pasa por aquí y no tiene
    # límite de páginas.
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        opciones = {"dpi": 150, "last_page": PAGINAS_OCR}
        if password:
            opciones["userpw"] = password
        paginas = convert_from_bytes(contenido, **opciones)
        return "\n".join(
            pytesseract.image_to_string(_preprocesar(p), lang="spa", config=PSM_COLUMNA_UNICA)
            for p in paginas
        )
    except Exception:  # noqa: BLE001 — el OCR depende de binarios externos (tesseract/poppler): si fallan, se devuelve lo que se pudo extraer
        return texto


# Etiquetas cuyo número al lado es un **documento**, no dinero: NIT, referencias, códigos,
# comprobantes, IP… Sin esto, el mayor número del texto gana y un pago de 844.041 se lee como
# 890.399.003 (el NIT) o como 260.930.020.535 (un consecutivo).
_LABEL_DOCUMENTO = re.compile(
    r"(?i)\b(?:nit|c[eé]dula|cc|referencia|consecutivo|c[oó]digo|cus|comprobante|factura|"
    r"resoluci[oó]n|autorizaci[oó]n|radicado|contrato|transacci[oó]n|aprobaci[oó]n|hash|"
    r"ip|tel[eé]fono|celular|whatsapp|sucursal|cajero|terminal|punto\s+de\s+venta)\b"
)


def detectar_monto(texto: str) -> Decimal | None:
    """Monto total del documento.

    El patrón anterior buscaba `total` en cualquier parte, sin límite de palabra, así
    que en un recibo con `SUBTOTAL 22.616` y `TOTAL 25.116` se quedaba con el
    **subtotal** (y encima lo leía como 22,6). Con `\btotal\b` no casa dentro de
    `SUBTOTAL`, pero sí en `Factura Total: 250.00`. Se toma el **último**: los recibos
    ponen el total al final, después de subtotal e impuestos.
    """
    formato = detectar_formato([texto])
    # Hay cajas que imprimen la etiqueta letra a letra: `T O T A L .... $1,188,248`. Se
    # busca en el texto original y en uno con esas letras sueltas ya pegadas.
    pegado = re.sub(
        r"\b(?:[A-Za-z]\s+){2,}[A-Za-z]\b", lambda m: m.group(0).replace(" ", ""), texto
    )
    for fuente in (pegado, texto):
        for patron in (
            r"(?i)\btotal(?:\s+a\s+pagar|\s+general|\s+neto)?\b[^\d]{0,25}(\d[\d.,]*)",
            r"(?i)\b(?:valor\s+total|importe\s+total|monto\s+total)\b[^\d]{0,25}(\d[\d.,]*)",
            # «Valor del Pago» / «Valor Pago» / «Valor a pagar»: así lo llaman los
            # comprobantes de pago de servicios (PSE, pasarelas)
            r"(?i)\bvalor\s+(?:del\s+)?pag(?:o|ar)\b[^\d]{0,25}(\d[\d.,]*)",
            r"(?i)\b(?:total\s+a\s+pagar|importe\s+a\s+pagar|monto\s+a\s+pagar)\b[^\d]{0,25}(\d[\d.,]*)",
            # «Monto:» / «Monto total» / «Monto del pago»: así lo llaman las confirmaciones
            # de pago («Monto: $46.477»). No se incluye «valor» a secas: «valor unitario» es
            # el precio de un artículo, no el total.
            r"(?i)\bmonto\b(?:\s+(?:total|del\s+pago|a\s+pagar))?[^\d]{0,25}(\d[\d.,]*)",
        ):
            encontrados = []
            for m in re.finditer(patron, fuente):
                # `TOTAL ITEMS 120` no es el monto de la factura: es cuántos artículos trae
                etiqueta = fuente[m.start() : m.start(1)]
                if re.match(r"(?i)\s*total\s+(?:items?|articulos?|unidades?|cantidad)", etiqueta):
                    continue
                encontrados.append(m.group(1))
            if encontrados:
                valor = parsear_monto(encontrados[-1], formato)
                if valor is not None:
                    return valor
    # 2) Sin etiqueta de total: se prefiere lo que esté escrito **como dinero** (con `$` o
    #    con centavos) y se descarta lo que es un número de **documento**.
    #
    #    Antes se tomaba el número más grande del texto, y en un comprobante de pago eso es
    #    un desastre: de `TR260930020535rBgAnc` salía 260.930.020.535 y del NIT
    #    `890399003-4` salía 890.399.003, mientras el pago real era 844.041.
    candidatos: list[tuple[Decimal, bool]] = []
    for m in re.finditer(r"(\$)?\s*(\d[\d.,]*)", texto):
        crudo = m.group(2)
        # Ojo: el patrón se come los espacios de delante, así que «pegado a una letra» hay que
        # mirarlo en el carácter justo anterior al **número** (`TOTAL 11.800` no está pegado).
        inicio = m.start(2)
        antes = texto[max(0, inicio - 26) : inicio]
        despues = texto[m.end() : m.end() + 6]
        # Pegado a letras = código (`TR260930020535`), no importe
        if (inicio and texto[inicio - 1].isalpha()) or re.match(r"[A-Za-z]", despues):
            continue
        # `890399003-4`: el guion es el dígito de verificación de un NIT
        if re.match(r"\s*-\s*\d", despues):
            continue
        # Cerca de una etiqueta de documento (Nit, Referencia, Consecutivo, CUS, IP…)
        if _LABEL_DOCUMENTO.search(antes):
            continue
        valor = parsear_monto(crudo, formato)
        if valor is None or valor <= 0:
            continue
        # Una pista de que es dinero: el símbolo o los centavos
        pista = bool(m.group(1)) or bool(re.search(r"[.,]\d{2}$", crudo))
        candidatos.append((valor, pista))

    con_pista = [v for v, pista in candidatos if pista]
    if con_pista:
        return max(con_pista)
    return max((v for v, _ in candidatos), default=None)


# Un monto por encima de esto no es un recibo ni una factura de consumo: es casi siempre un
# número de documento (un NIT, una referencia, un consecutivo) mal leído.
MONTO_INVEROSIMIL = Decimal("100000000")
# Y si el monto no coincide con la suma de los artículos, se avisa. El margen es ancho a
# propósito: en una factura con IVA o descuento las líneas **no** suman el total, y eso es
# normal; lo que no es normal es una diferencia de un 25 %.
MARGEN_LINEAS = Decimal("0.25")


def aviso_del_monto(
    monto: Decimal | None, texto: str, suma_lineas: Decimal | None = None
) -> str | None:
    """Dice si el monto detectado **no es de fiar** (y por qué). `None` si está bien.

    La app no inventa números: cuando el monto sale de un número de documento, cuando es
    absurdamente grande o cuando no cuadra con los artículos, lo dice para que el usuario lo
    corrija **antes** de registrar el gasto. Las facturas viejas leídas con una versión
    anterior del lector son justo las que caen aquí.
    """
    if monto is None:
        return (
            "No pudimos leer el monto en este documento: escríbelo en «✏️ Corregir» para que "
            "la factura y el gasto cuadren."
        )
    if monto >= MONTO_INVEROSIMIL:
        return (
            f"El monto detectado ({monto:,.2f}) es altísimo para este documento: mira que no "
            "sea un número de referencia (NIT, consecutivo, comprobante) y corrígelo."
        )

    # ¿De dónde salió ese número? Si todas sus apariciones en el texto están pegadas a una
    # etiqueta de documento, no es un monto.
    if texto:
        formato = detectar_formato([texto])
        apariciones = 0
        pegadas = 0
        for m in re.finditer(r"(\$)?\s*(\d[\d.,]*)", texto):
            if parsear_monto(m.group(2), formato) != monto:
                continue
            apariciones += 1
            inicio = m.start(2)
            antes = texto[max(0, inicio - 26) : inicio]
            despues = texto[m.end() : m.end() + 6]
            if (
                _LABEL_DOCUMENTO.search(antes)
                or (inicio and texto[inicio - 1].isalpha())
                or re.match(r"\s*-\s*\d", despues)
            ):
                pegadas += 1
        if apariciones and pegadas == apariciones:
            return (
                f"El monto detectado ({monto:,.2f}) sale de un número de documento (NIT, "
                "referencia o comprobante), no del valor pagado: corrígelo."
            )

    if suma_lineas is not None and suma_lineas > 0:
        diferencia = abs(monto - suma_lineas)
        if diferencia > max(Decimal("1000"), abs(monto) * MARGEN_LINEAS):
            return (
                f"El monto detectado ({monto:,.2f}) no coincide con la suma de los artículos "
                f"({suma_lineas:,.2f}): revisa cuál de los dos está mal (si la factura tiene "
                "impuestos o descuentos, la diferencia es normal)."
            )
    return None


def detectar_fecha(texto: str) -> date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # `2026/9/16` (año de 4 cifras primero): sin esto, la fecha caía en el patrón
    # ambiguo `D/M/Y` de abajo y se leía como 26/9/2016.
    m = re.search(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})", texto)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    m = re.search(r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})", texto)
    if m:
        d, mes, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        try:
            return date(y, mes, d)
        except ValueError:
            pass
    return None


def nombre_factura(nombre_archivo: str) -> str:
    """De `Mercado_Septiembre_quincena 1.pdf` a `Mercado Septiembre quincena 1`."""
    base = nombre_archivo.rsplit(".", 1)[0]
    return base.replace("_", " ").strip() or "Factura"
