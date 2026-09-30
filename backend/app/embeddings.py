"""Embeddings opcionales para clasificar los artículos de una factura.

Tercer nivel del clasificador (`clasificador.clasificar`): similitud semántica
entre la descripción del artículo y el nombre (más su diccionario) de cada
etiqueta del usuario.

Es **opcional por diseño**:

- Si `FINANZAS_OLLAMA_URL` no está configurado, `make_embedding()` devuelve
  `None` y el clasificador se queda en historial + diccionario, sin tocar la red.
- Si Ollama no responde, `embed()` devuelve `None` y ese nivel se salta: una
  factura nunca falla porque el servicio de embeddings esté caído.
- Los vectores se cachean por texto: el perfil de cada etiqueta se pide una sola
  vez por proceso, no una vez por línea de la factura.

Se usa `urllib` (biblioteca estándar) para no añadir dependencias de red.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from functools import lru_cache

from .config import get_settings

Embedding = Callable[[str], list[float] | None]


def make_embedding(timeout: float | None = None) -> Embedding | None:
    """Devuelve el embedder configurado, o `None` si no hay Ollama configurado.

    `timeout` se puede subir para usos que no son por línea de factura (por ejemplo indexar el
    manual de ayuda, donde una espera larga no molesta a nadie): para el clasificador se queda el
    valor corto de siempre, porque ahí sí molesta.
    """
    settings = get_settings()
    if not settings.ollama_url:
        return None

    url = f"{settings.ollama_url.rstrip('/')}/api/embeddings"
    modelo = settings.ollama_embedding_model
    espera = timeout if timeout is not None else settings.ollama_timeout

    @lru_cache(maxsize=1024)
    def _embed_crudo(texto: str) -> tuple[float, ...] | None:
        payload = json.dumps({"model": modelo, "prompt": texto}).encode("utf-8")
        peticion = urllib.request.Request(
            url, data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(peticion, timeout=espera) as respuesta:
                vector = json.loads(respuesta.read().decode("utf-8"))["embedding"]
        except (urllib.error.URLError, OSError, ValueError, KeyError, TimeoutError):
            return None  # sin Ollama: el clasificador sigue con los otros niveles
        if not isinstance(vector, list) or not vector:
            return None
        return tuple(float(x) for x in vector)

    def embed(texto: str, tipo: str = "documento") -> list[float] | None:
        # Prefijo de tarea de nomic-embed-text: rinde mejor separando documento
        # y consulta. Con otros modelos es inocuo.
        prefijo = "search_query" if tipo == "consulta" else "search_document"
        vector = _embed_crudo(f"{prefijo}: {texto}")
        return list(vector) if vector is not None else None

    return embed


def parecido(a: list[float] | None, b: list[float] | None) -> float:
    """Similitud del coseno entre dos vectores (0 si falta alguno)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    producto = sum(x * y for x, y in zip(a, b, strict=False))
    norma_a = sum(x * x for x in a) ** 0.5
    norma_b = sum(y * y for y in b) ** 0.5
    if not norma_a or not norma_b:
        return 0.0
    return producto / (norma_a * norma_b)
