"""Cobros: comprar un plan o un paquete de lecturas.

El precio **no lo manda el cliente**: se lee del catálogo (planes y paquetes en la base). El
circuito es: se crea la orden → se paga en la pasarela → la pasarela avisa → se acredita **una
sola vez**.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import pagos as cobros
from .. import pasarelas
from ..config import get_settings
from ..deps import get_current_user, get_db, usuario_opcional
from ..models import Usuario
from ..schemas import OrdenPagoIn, OrdenPagoOut, PagoOut, PaqueteLecturasOut

router = APIRouter(prefix="/pagos", tags=["pagos"])


def _pasarela():
    try:
        return pasarelas.pasarela_actual()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/paquetes", response_model=list[PaqueteLecturasOut])
def listar_paquetes(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Los paquetes de lecturas que se pueden comprar aparte del plan."""
    return cobros.paquetes(db)


@router.get("/mios", response_model=list[PagoOut])
def mis_pagos(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Los recibos: qué compró, cuánto costó y cuándo (el historial)."""
    return cobros.historial(db, user)


@router.post("/orden", response_model=OrdenPagoOut, status_code=201)
def crear_orden(
    data: OrdenPagoIn,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Crea la orden de compra y devuelve cómo pagarla."""
    pasarela = _pasarela()
    pago, datos = cobros.crear_orden(db, user, data.tipo, data.codigo)
    return OrdenPagoOut(
        referencia=pago.referencia,
        tipo=pago.tipo,
        codigo=pago.codigo,
        monto=pago.monto,
        moneda=pago.moneda,
        estado=pago.estado,
        pasarela=pasarela.nombre,
        url=datos.get("url"),
        instrucciones=datos.get("instrucciones"),
    )


@router.post("/webhook/{nombre_pasarela}")
async def aviso_de_pago(
    nombre_pasarela: str,
    request: Request,
    db: Session = Depends(get_db),
    user: Usuario | None = Depends(usuario_opcional),
):
    """Aviso de la pasarela: si es auténtico, se acredita lo comprado (una sola vez).

    Con una pasarela real no pide sesión: la llama la pasarela y la autenticidad la da **su
    firma**. Con la **simulada** sí pide sesión: no hay firma que valga, así que sin ella
    cualquiera con una referencia podría acreditarse lecturas (sería un agujero).
    """
    pasarela = _pasarela()
    if nombre_pasarela != pasarela.nombre:
        raise HTTPException(status_code=404, detail="Esa pasarela no es la configurada")

    if pasarela.nombre == "simulada" and user is None:
        raise HTTPException(
            status_code=401,
            detail="La pasarela simulada exige sesión: sin firma, el aviso lo tiene que firmar el usuario.",
        )

    cuerpo = await request.body()
    if not pasarela.verificar(cuerpo, dict(request.headers)):
        raise HTTPException(status_code=401, detail="El aviso no viene de la pasarela")

    datos = pasarela.interpretar(cuerpo)
    pago = cobros.por_referencia(db, datos.get("referencia") or "", bloquear=True)
    if pago is None:
        raise HTTPException(status_code=404, detail="No hay ninguna orden con esa referencia")

    if datos.get("estado") != "pagado":
        cobros.marcar_fallido(db, pago, datos.get("motivo") or "La pasarela reportó un fallo")
        return {"ok": True, "estado": pago.estado}

    pago, mensaje, nuevo = cobros.aplicar_pago(db, pago, datos.get("id_externo"))
    return {"ok": True, "estado": pago.estado, "mensaje": mensaje, "aplicado_ahora": nuevo}


@router.post("/simular-pago/{referencia}")
def simular_pago(
    referencia: str,
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Confirma un pago **con la pasarela simulada** (para probar el circuito sin llaves).

    Con una pasarela real esto no existe: responde 403, porque acreditar sin cobrar sería un
    agujero.
    """
    ajustes = get_settings()
    if (ajustes.pasarela or "").lower() != "simulada" or not ajustes.pasarela_simulada_permitida:
        raise HTTPException(
            status_code=403,
            detail="La confirmación simulada solo existe con la pasarela simulada.",
        )
    pago = cobros.por_referencia(db, referencia)
    if pago is None or pago.usuario_id != user.id:
        raise HTTPException(status_code=404, detail="Esa orden no existe o no es tuya")
    pago, mensaje, _nuevo = cobros.aplicar_pago(db, pago, id_externo=f"simulado-{pago.referencia[:12]}")
    return {"ok": True, "estado": pago.estado, "mensaje": mensaje}
