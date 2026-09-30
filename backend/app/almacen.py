"""Dónde viven los archivos de las facturas.

Hoy es el **disco local** de la máquina (que en la definitiva tendrá 500 GB o más), pero detrás
de una interfaz: el resto de la app pide «guarda esto con esta clave» y no sabe si mañana eso es
un disco, un almacén de objetos o los dos a la vez. La ruta sale de la configuración, nunca del
código, para que la mudanza de servidor sea copiar una carpeta.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from .config import get_settings


class ArchivoNoEncontrado(RuntimeError):
    """El archivo ya no está: se venció la retención o el usuario lo borró."""


def _raiz() -> Path:
    raiz = Path(get_settings().almacen_ruta)
    raiz.mkdir(parents=True, exist_ok=True)
    return raiz


def clave_de(usuario_id, factura_id, nombre: str) -> str:
    """La clave del archivo: por usuario y factura, con la extensión original.

    Se agrupa por usuario para poder borrar todo lo suyo de una vez, y se guarda el nombre
    original solo como extensión (el nombre real va en la factura).
    """
    sufijo = Path(nombre).suffix.lower()[:10] or ".bin"
    return f"{usuario_id}/{factura_id}{sufijo}"


def _ruta(clave: str) -> Path:
    raiz = _raiz().resolve()
    destino = (raiz / clave).resolve()
    # Defensa simple: una clave no puede salirse de la carpeta del almacén
    if raiz not in destino.parents:
        raise ValueError("Clave de almacén inválida")
    return destino


def guardar(clave: str, contenido: bytes) -> int:
    """Guarda el archivo y devuelve su tamaño en bytes."""
    destino = _ruta(clave)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(contenido)
    return len(contenido)


def leer(clave: str) -> bytes:
    destino = _ruta(clave)
    if not destino.is_file():
        raise ArchivoNoEncontrado(
            "El archivo de esta factura ya no está guardado (se cumplió el tiempo de retención "
            "o lo borraste). Vuelve a subirlo si lo necesitas."
        )
    return destino.read_bytes()


def borrar(clave: str) -> None:
    destino = _ruta(clave)
    destino.unlink(missing_ok=True)
    # Si era el último archivo del usuario, se va también su carpeta: si no, quedan miles de
    # carpetas vacías que nadie limpia.
    padre = destino.parent
    raiz = _raiz().resolve()
    if padre != raiz and padre.is_dir() and not any(padre.iterdir()):
        padre.rmdir()


def huella(contenido: bytes) -> str:
    """Huella del contenido: sirve para detectar el mismo archivo subido dos veces."""
    return hashlib.sha256(contenido).hexdigest()[:32]
