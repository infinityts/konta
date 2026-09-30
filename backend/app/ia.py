"""Lectura de facturas con un modelo de visión (opcional).

Es la **segunda opinión** para los documentos que el OCR local no puede: manuscritos, fotos
torcidas, recibos de un formato raro. No sustituye al lector de siempre: se pide a propósito,
cuesta dinero y está limitado por el plan del usuario.

Dos reglas de diseño:

1. **No decide**: devuelve lo que lee (texto y campos) y la app aplica **sus** reglas
   (plausibilidad del monto, tipo de documento, avisos). El modelo no inventa cifras que se
   guarden sin pasar por el mismo control que todo lo demás.
2. **No se cobra por lo que falla**: el consumo del plan se descuenta solo cuando la lectura
   sale bien.
"""

from __future__ import annotations

import base64
import io
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal

import httpx

from .config import get_settings

# Lo que se le pide al modelo. Corto a propósito: cada palabra del prompt se paga en cada
# lectura, y el prompt se cachea (la parte repetida cuesta una décima parte).
INSTRUCCIONES = (
    "Eres un lector de facturas y recibos colombianos. Devuelve SOLO un JSON válido, sin "
    "explicaciones ni markdown, con esta forma exacta:\n"
    '{"texto": "transcripción literal de todo el texto visible", '
    '"monto": número o null (el TOTAL pagado, no subtotales ni impuestos), '
    '"fecha": "AAAA-MM-DD" o null, "emisor": "nombre del comercio" o null, '
    '"nit": "NIT del emisor" o null, '
    '"lineas": [{"descripcion": "artículo", "valor": número}]}\n'
    "Reglas: si un dato no se ve con claridad, pon null en vez de inventarlo. El monto es el "
    "total final. No incluyas los artículos si el documento es un recibo de pago de servicio."
)

TIPOS_IMAGEN = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@dataclass
class LecturaIa:
    """Lo que devolvió el modelo, con lo que costó."""

    texto: str = ""
    campos: dict = field(default_factory=dict)
    tokens_entrada: int = 0
    tokens_salida: int = 0
    costo_usd: Decimal = Decimal("0")


class IaNoConfigurada(RuntimeError):
    """No hay clave del proveedor: la función está apagada, no rota."""


def configurada() -> bool:
    return bool(get_settings().ia_api_key.strip())


def _a_imagen(contenido: bytes, tipo: str | None) -> tuple[str, str]:
    """Devuelve (mime, base64). El proveedor solo acepta imágenes: un PDF se convierte.

    Se reutiliza el mismo `pdf2image` que el OCR local (ya está instalado por él), con la
    primera página: una factura de varios folios se lee folio a folio si hace falta.
    """
    if (tipo or "").lower() in TIPOS_IMAGEN:
        return (tipo or "image/jpeg").lower(), base64.b64encode(contenido).decode()

    from pdf2image import convert_from_bytes

    paginas = convert_from_bytes(contenido, dpi=150, last_page=1)
    if not paginas:
        raise ValueError("No pudimos convertir el documento en una imagen")
    buffer = io.BytesIO()
    paginas[0].convert("RGB").save(buffer, format="JPEG", quality=85)
    return "image/jpeg", base64.b64encode(buffer.getvalue()).decode()


def _json_de(texto: str) -> dict:
    """Saca el JSON de la respuesta, aunque venga envuelto en texto o en ```."""
    limpio = re.sub(r"```(?:json)?", "", texto).strip()
    inicio, fin = limpio.find("{"), limpio.rfind("}")
    if inicio == -1 or fin == -1:
        raise ValueError("El modelo no devolvió un JSON con la lectura")
    return json.loads(limpio[inicio : fin + 1])


def _decimal(valor) -> Decimal | None:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor).replace(".", "").replace(",", ".")) if isinstance(valor, str) else Decimal(str(valor))
    except Exception:  # noqa: BLE001 — un valor raro se trata como «no lo sé», no rompe la lectura
        return None


def leer_documento(contenido: bytes, nombre: str, tipo: str | None) -> LecturaIa:
    """Manda el documento al modelo de visión y devuelve su lectura.

    Lanza `IaNoConfigurada` si no hay clave. Un fallo del proveedor se propaga como error: el
    usuario no paga por una lectura que no ocurrió.
    """
    ajustes = get_settings()
    if not configurada():
        raise IaNoConfigurada(
            "La lectura con IA no está configurada en este servidor (falta la clave del "
            "proveedor). El lector normal de Konta sigue funcionando."
        )

    mime, datos = _a_imagen(contenido, tipo)
    peticion = {
        "model": ajustes.ia_modelo,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": INSTRUCCIONES},
                    {
                        "type": "image_url",
                        # `auto` mantiene la resolución original: el proveedor ya limita la
                        # imagen a ~1024 tokens, así que bajar la calidad no ahorra nada.
                        "image_url": {"url": f"data:{mime};base64,{datos}", "detail": "auto"},
                    },
                ],
            }
        ],
    }
    with httpx.Client(timeout=120) as cliente:
        respuesta = cliente.post(
            f"{ajustes.ia_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {ajustes.ia_api_key}"},
            json=peticion,
        )
    respuesta.raise_for_status()
    cuerpo = respuesta.json()

    uso = cuerpo.get("usage") or {}
    entrada = int(uso.get("prompt_tokens") or 0)
    salida = int(uso.get("completion_tokens") or 0)
    costo = (entrada / 1_000_000) * ajustes.ia_precio_entrada
    costo += (salida / 1_000_000) * ajustes.ia_precio_salida

    bruto = (cuerpo.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    try:
        datos_leidos = _json_de(bruto)
    except (ValueError, json.JSONDecodeError):
        # Si no hubo JSON, al menos queda la transcripción para que el usuario trabaje con ella
        datos_leidos = {"texto": bruto, "monto": None, "fecha": None}

    lineas = []
    for fila in datos_leidos.get("lineas") or []:
        if not isinstance(fila, dict) or not fila.get("descripcion"):
            continue
        valor = _decimal(fila.get("valor"))
        if valor is None or valor <= 0:
            continue
        lineas.append({"descripcion": str(fila["descripcion"])[:200], "valor": valor})

    return LecturaIa(
        texto=str(datos_leidos.get("texto") or "")[:20000],
        campos={
            "monto": _decimal(datos_leidos.get("monto")),
            "fecha": datos_leidos.get("fecha"),
            "emisor": (str(datos_leidos["emisor"])[:140] if datos_leidos.get("emisor") else None),
            "nit": (str(datos_leidos["nit"])[:40] if datos_leidos.get("nit") else None),
            "lineas": lineas,
        },
        tokens_entrada=entrada,
        tokens_salida=salida,
        costo_usd=Decimal(str(round(costo, 6))),
    )
