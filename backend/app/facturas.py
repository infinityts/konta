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
from decimal import Decimal, InvalidOperation

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


def extraer_texto(contenido: bytes, nombre: str = "", content_type: str | None = None) -> str:
    """Devuelve el texto de un PDF o de una foto de recibo."""
    if es_imagen(nombre, content_type):
        try:
            from PIL import Image

            return _ocr_imagen(Image.open(io.BytesIO(contenido)))
        except Exception:
            return ""

    # 1. PDF digital
    texto = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contenido))
        texto = "\n".join((pagina.extract_text() or "") for pagina in reader.pages)
    except Exception:
        texto = ""

    if texto.strip():
        return texto

    # 2. PDF escaneado -> OCR
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        paginas = convert_from_bytes(contenido)
        return "\n".join(pytesseract.image_to_string(_preprocesar(p), lang="spa") for p in paginas)
    except Exception:
        return texto


def _parse_monto(texto: str) -> Decimal | None:
    s = texto.strip()
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def detectar_monto(texto: str) -> Decimal | None:
    m = re.search(
        r"(?:total|valor|monto|importe|a pagar)[^\d]{0,25}(\d[\d.,]*)",
        texto,
        re.IGNORECASE,
    )
    if m:
        v = _parse_monto(m.group(1))
        if v is not None:
            return v
    # Fallback: el número con formato de dinero más grande
    candidatos = re.findall(r"\d[\d.,]{2,}", texto)
    valores = [v for v in (_parse_monto(c) for c in candidatos) if v is not None]
    return max(valores) if valores else None


def detectar_fecha(texto: str) -> date | None:
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texto)
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
