"""QR de una factura electrónica colombiana (DIAN).

Una factura electrónica (o un documento equivalente POS, como el recibo de un
parqueadero) trae un **QR** con la URL de consulta de la DIAN:

    https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey=<CUDE/CUFE>

De ahí se saca el **CUDE** (el código único del documento), que sirve para dos cosas:

1. **No depender del OCR**: el código viene del QR, no de adivinar caracteres.
2. **Detectar duplicados**: si el mismo documento se sube dos veces, el CUDE es el mismo.

La descarga del PDF oficial desde la DIAN **requiere sesión** (`/User/SearchDocument`
devuelve el formulario de acceso), así que aquí solo se guarda el enlace: la app lo
muestra para que el usuario abra el documento con su cuenta y, si quiere el detalle
exacto, suba ese PDF (que se lee perfecto, porque es digital).
"""

from __future__ import annotations

import re

# El `documentkey` del catálogo, o el CUFE/CUDE suelto
PATRON_KEY = re.compile(r"documentkey=([0-9a-fA-F]{40,96})", re.IGNORECASE)
PATRON_CUDE = re.compile(r"\b([0-9a-fA-F]{96})\b")
PATRON_URL_DIAN = re.compile(r"https?://[^\s\"'<>]*dian\.gov\.co[^\s\"'<>]*", re.IGNORECASE)


def cude_de_url(url: str | None) -> str | None:
    """CUDE/CUFE que viene en la URL del QR (o en el propio texto del QR)."""
    if not url:
        return None
    m = PATRON_KEY.search(url)
    if m:
        return m.group(1).lower()
    m = PATRON_CUDE.search(url)
    return m.group(1).lower() if m else None


def url_dian(texto_qr: str | None) -> str | None:
    """La URL oficial de consulta que trae el QR."""
    if not texto_qr:
        return None
    m = PATRON_URL_DIAN.search(texto_qr)
    return m.group(0) if m else None


def leer_qr(imagen) -> str | None:
    """Texto del primer QR de una imagen (o `None` si no hay o falta el lector)."""
    try:
        import zxingcpp
    except Exception:  # noqa: BLE001 — el lector es opcional: sin él, la app sigue igual
        return None
    try:
        resultados = zxingcpp.read_barcodes(imagen)
    except Exception:  # noqa: BLE001 — una imagen rara no debe tumbar la subida
        return None
    return resultados[0].text if resultados else None


def qr_de_documento(contenido: bytes, nombre: str = "", content_type: str | None = None) -> str | None:
    """Texto del QR de una **foto** o de la primera página de un **PDF**."""
    from .facturas import es_imagen

    if es_imagen(nombre, content_type):
        try:
            import io

            from PIL import Image

            return leer_qr(Image.open(io.BytesIO(contenido)))
        except Exception:  # noqa: BLE001
            return None

    try:
        from pdf2image import convert_from_bytes

        paginas = convert_from_bytes(contenido, first_page=1, last_page=1)
        return leer_qr(paginas[0]) if paginas else None
    except Exception:  # noqa: BLE001 — un PDF sin imágenes o sin poppler no es un error fatal
        return None
