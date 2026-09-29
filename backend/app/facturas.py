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


def _ocr_imagen(imagen) -> str:
    import pytesseract

    return pytesseract.image_to_string(_preprocesar(imagen), lang="spa")


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
        texto = "\n".join((pagina.extract_text() or "") for pagina in reader.pages)
    except ValueError:
        raise  # la contraseña es un dato de la subida, no un PDF raro
    except Exception:  # noqa: BLE001 — el OCR depende de binarios externos (tesseract/poppler): si fallan, se devuelve lo que se pudo extraer
        texto = ""

    if texto.strip():
        return texto

    # 2. PDF escaneado -> OCR
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        paginas = (
            convert_from_bytes(contenido, userpw=password)
            if password
            else convert_from_bytes(contenido)
        )
        return "\n".join(pytesseract.image_to_string(_preprocesar(p), lang="spa") for p in paginas)
    except Exception:  # noqa: BLE001 — el OCR depende de binarios externos (tesseract/poppler): si fallan, se devuelve lo que se pudo extraer
        return texto


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
    # Fallback: el número con formato de dinero más grande
    candidatos = re.findall(r"\d[\d.,]{2,}", texto)
    valores = [v for v in (parsear_monto(c, formato) for c in candidatos) if v is not None]
    return max(valores) if valores else None


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
