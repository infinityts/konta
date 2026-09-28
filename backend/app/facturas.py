"""Extracción de datos de facturas PDF.

1. Intenta extraer el texto con `pypdf` (PDFs digitales).
2. Si no hay texto (PDF escaneado), intenta OCR con `pytesseract` + `pdf2image`
   (requiere los binarios `tesseract-ocr` y `poppler-utils`).
3. Aplica heurísticas para detectar monto y fecha.
"""

from __future__ import annotations

import io
import re
from datetime import date
from decimal import Decimal, InvalidOperation


def extraer_texto(contenido: bytes) -> str:
    texto = ""
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(contenido))
        texto = "\n".join((pagina.extract_text() or "") for pagina in reader.pages)
    except Exception:
        texto = ""

    if texto.strip():
        return texto

    # Fallback OCR para PDFs escaneados
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        paginas = convert_from_bytes(contenido)
        return "\n".join(pytesseract.image_to_string(p, lang="spa") for p in paginas)
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
