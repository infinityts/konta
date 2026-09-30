"""Un archivo demasiado grande tiene que decirlo claro, no dar un error opaco.

Las fotos de un móvil pesan más de 1 MB y nginx corta por defecto en 1 MB: la subida fallaba
con un 413 en HTML, el navegador no podía leerlo y no aparecía ni la factura ni el botón
«Leer líneas». Aquí se prueba el aviso del backend (nginx ya no corta antes).
"""

from __future__ import annotations

from test_api import _registrar

LIMITE_MB = 15


def test_una_foto_demasiado_grande_lo_dice_claro(client):
    _, h = _registrar(client)
    grande = b"\x89PNG\r\n\x1a\n" + b"\x00" * ((LIMITE_MB + 1) * 1024 * 1024)
    r = client.post(
        "/facturas", headers=h, files={"archivo": ("foto.png", grande, "image/png")}
    )
    assert r.status_code == 413, r.text
    detalle = r.json()["detail"]
    assert "MB" in detalle and "calidad" in detalle


def test_una_foto_normal_sube(client):
    _, h = _registrar(client)
    normal = b"\x89PNG\r\n\x1a\n" + b"\x00" * (512 * 1024)
    r = client.post(
        "/facturas", headers=h, files={"archivo": ("foto.png", normal, "image/png")}
    )
    assert r.status_code == 201, r.text
