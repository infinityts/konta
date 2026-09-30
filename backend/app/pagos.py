"""El cobro: crear la orden, aplicar el pago y llevar el historial.

Dos reglas que protegen el dinero y la confianza:

1. **Idempotencia**: cada orden lleva una `referencia` que viaja a la pasarela y vuelve en su
   aviso. Un aviso repetido (las pasarelas reintentan) encuentra la orden ya `aplicado` y **no**
   vuelve a acreditar.
2. **Nada se acredita sin pago**: el plan o las lecturas se suman solo cuando el pago queda
   `pagado`, y queda dicho cuándo y con qué identificador de la pasarela.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Pago, PaqueteLecturas, Plan, Usuario
from .pasarelas import pasarela_actual

PLAN = "plan"
PAQUETE = "paquete"
PENDIENTE = "pendiente"
PAGADO = "pagado"
FALLIDO = "fallido"


def paquetes(db: Session) -> list[PaqueteLecturas]:
    return list(
        db.scalars(
            select(PaqueteLecturas)
            .where(PaqueteLecturas.activo.is_(True))
            .order_by(PaqueteLecturas.orden)
        ).all()
    )


def _precio_de(db: Session, tipo: str, codigo: str) -> tuple[object, str]:
    """El catálogo manda: el precio no lo pone el cliente, se lee de la base."""
    if tipo == PLAN:
        plan = db.get(Plan, codigo)
        if plan is None or not plan.activo:
            raise HTTPException(status_code=404, detail=f"El plan {codigo} no existe")
        return plan, plan.nombre
    paquete = db.get(PaqueteLecturas, codigo)
    if paquete is None or not paquete.activo:
        raise HTTPException(status_code=404, detail=f"El paquete {codigo} no existe")
    return paquete, paquete.nombre


def crear_orden(db: Session, usuario: Usuario, tipo: str, codigo: str) -> tuple[Pago, dict]:
    """Crea la orden y le pide a la pasarela cómo pagarla."""
    if tipo not in (PLAN, PAQUETE):
        raise HTTPException(status_code=400, detail="El tipo tiene que ser «plan» o «paquete»")

    catalogo, nombre = _precio_de(db, tipo, codigo)
    pasarela = pasarela_actual()
    pago = Pago(
        usuario_id=usuario.id,
        referencia=f"konta-{uuid.uuid4().hex[:20]}",
        tipo=tipo,
        codigo=codigo,
        monto=getattr(catalogo, "precio_mes", None) or catalogo.precio,
        pasarela=pasarela.nombre,
        detalle=json.dumps({"nombre": nombre}, ensure_ascii=False),
    )
    db.add(pago)
    db.flush()
    datos = pasarela.crear_pago(pago)
    db.commit()
    db.refresh(pago)
    return pago, datos


def _acreditar(db: Session, pago: Pago) -> str:
    """Suma lo comprado: el plan, o las lecturas al saldo."""
    usuario = db.get(Usuario, pago.usuario_id)
    if usuario is None:
        raise HTTPException(status_code=404, detail="El usuario del pago ya no existe")

    if pago.tipo == PLAN:
        usuario.plan_codigo = pago.codigo
        return f"Plan cambiado a {pago.codigo}"
    paquete = db.get(PaqueteLecturas, pago.codigo)
    lecturas = paquete.lecturas if paquete else 0
    usuario.lecturas_extra = (usuario.lecturas_extra or 0) + lecturas
    return f"Sumadas {lecturas} lecturas al saldo"


def aplicar_pago(db: Session, pago: Pago, id_externo: str | None = None) -> tuple[Pago, str, bool]:
    """Marca el pago como pagado y acredita lo comprado **una sola vez**.

    Devuelve (pago, mensaje, si_era_nuevo). Si ya estaba aplicado, no toca nada: es la garantía
    contra el doble cobro cuando la pasarela reintenta el aviso.
    """
    if pago.aplicado:
        return pago, "El pago ya estaba aplicado: no se volvió a acreditar", False

    mensaje = _acreditar(db, pago)
    pago.estado = PAGADO
    pago.aplicado = True
    pago.pagado_en = datetime.now(UTC)
    if id_externo:
        pago.id_externo = id_externo[:120]
    db.commit()
    db.refresh(pago)
    return pago, mensaje, True


def marcar_fallido(db: Session, pago: Pago, motivo: str = "") -> Pago:
    if not pago.aplicado:
        pago.estado = FALLIDO
        pago.detalle = json.dumps({"motivo": motivo[:300]}, ensure_ascii=False)
        db.commit()
        db.refresh(pago)
    return pago


def por_referencia(db: Session, referencia: str) -> Pago | None:
    return db.scalar(select(Pago).where(Pago.referencia == referencia))


def historial(db: Session, usuario: Usuario) -> list[Pago]:
    """Los recibos del usuario: qué compró, cuánto y cuándo."""
    return list(
        db.scalars(
            select(Pago).where(Pago.usuario_id == usuario.id).order_by(Pago.creado_en.desc())
        ).all()
    )
