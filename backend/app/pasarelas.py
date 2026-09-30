"""Las pasarelas de pago, detrás de una interfaz.

El circuito del cobro (orden → aviso → acreditar) es igual para todas; lo que cambia es cómo se
pide el pago y cómo se verifica que el aviso es auténtico. Aquí vive esa parte, para que conectar
Wompi, MercadoPago o PayU sea escribir una clase y cambiar una variable — no tocar el cobro.

Hoy solo está la **simulada**, que sirve para probar el circuito completo sin llaves. Las reales
necesitan las credenciales del comercio y su documentación: se enchufan aquí.
"""

from __future__ import annotations

from typing import Protocol

from .config import get_settings


class Pasarela(Protocol):
    """Lo que la app espera de cualquier pasarela."""

    nombre: str

    def crear_pago(self, pago) -> dict:
        """Datos para que el usuario pague: la URL de la pasarela y lo que haga falta."""

    def verificar(self, cuerpo: bytes, cabeceras: dict) -> bool:
        """Comprueba que el aviso viene de la pasarela y no de cualquiera."""

    def interpretar(self, cuerpo: bytes) -> dict:
        """Traduce el aviso de la pasarela a lo que la app entiende.

        Devuelve `referencia`, `id_externo` y `estado` (pagado o fallido). Cada pasarela tiene su
        formato: por eso esto vive aquí y no en el cobro.
        """


class PasarelaSimulada:
    """Para probar el circuito sin llaves: el «pago» se confirma desde la propia app.

    No cobra nada: acredita el plan o las lecturas como si la pasarela hubiera avisado. Solo se
    usa cuando `FINANZAS_PASARELA=simulada`, que es el valor por defecto en desarrollo y pruebas.
    """

    nombre = "simulada"

    def crear_pago(self, pago) -> dict:
        return {
            "pasarela": self.nombre,
            "referencia": pago.referencia,
            "monto": float(pago.monto),
            "moneda": pago.moneda,
            "url": None,
            "instrucciones": (
                "Pasarela simulada: el pago se confirma desde la app "
                f"con POST /pagos/simular-pago/{pago.referencia}."
            ),
        }

    def verificar(self, cuerpo: bytes, cabeceras: dict) -> bool:
        return True

    def interpretar(self, cuerpo: bytes) -> dict:
        import json

        datos = json.loads(cuerpo or b"{}")
        return {
            "referencia": str(datos.get("referencia") or ""),
            "id_externo": str(datos.get("id_externo") or "") or None,
            "estado": "pagado" if datos.get("estado", "pagado") == "pagado" else "fallido",
            "motivo": str(datos.get("motivo") or ""),
        }


def pasarela_actual() -> Pasarela:
    """La pasarela configurada. Si piden una real y no está implementada, se dice."""
    nombre = (get_settings().pasarela or "simulada").strip().lower()
    if nombre == "simulada":
        return PasarelaSimulada()
    raise RuntimeError(
        f"La pasarela «{nombre}» todavía no está enchufada. Se conecta en app/pasarelas.py con "
        "las credenciales del comercio (y su documentación a mano)."
    )
