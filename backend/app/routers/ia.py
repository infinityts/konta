"""Lectura de facturas con IA, con **cuota por plan**.

La IA es la segunda opinión para los documentos que el OCR local no puede. Aquí está el
control: se comprueba el cupo **antes** de llamar al proveedor (para no gastar un token de
más), se descuenta **solo si la lectura sale bien** y se anota lo que costó de verdad.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import cuotas, ia
from ..config import get_settings
from ..deps import get_current_user, get_db
from ..facturas import aviso_de_la_fecha, aviso_del_monto, detectar_emisor, detectar_monto
from ..lineas import detectar_tipo
from ..models import Factura, FacturaLinea, Plan, Usuario
from ..recurrencia import hoy
from ..schemas import CuotaOut, FacturaDetalleOut, PlanOut

router = APIRouter(prefix="/ia", tags=["ia"])


def _cuota_out(resumen: dict) -> CuotaOut:
    return CuotaOut(
        periodo=resumen["periodo"],
        plan=resumen["plan"],
        plan_nombre=resumen["plan_nombre"],
        precio_mes=resumen["precio_mes"],
        lecturas_incluidas=resumen["lecturas"]["incluidas"],
        lecturas_usadas=resumen["lecturas"]["usadas"],
        lecturas_extra=resumen["lecturas"]["extra"],
        lecturas_restantes=resumen["lecturas"]["restantes"],
        consultas_incluidas=resumen["consultas"]["incluidas"],
        consultas_usadas=resumen["consultas"]["usadas"],
        consultas_restantes=resumen["consultas"]["restantes"],
        tokens_entrada=resumen["tokens_entrada"],
        tokens_salida=resumen["tokens_salida"],
        costo_usd=resumen["costo_usd"],
        archivos_usados=resumen["archivos_usados"],
        archivos_incluidos=resumen["archivos_incluidos"],
        mb_usados=resumen["mb_usados"],
        mb_incluidos=resumen["mb_incluidos"],
        retencion_dias=resumen["retencion_dias"],
    )


@router.get("/planes", response_model=list[PlanOut])
def listar_planes(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """El catálogo de planes: los límites salen de la base, no del código."""
    return list(
        db.scalars(select(Plan).where(Plan.activo.is_(True)).order_by(Plan.orden)).all()
    )


@router.get("/cuota", response_model=CuotaOut)
def ver_cuota(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Lo que le queda este mes (para enseñarlo en la app antes de que se agote)."""
    return _cuota_out(cuotas.resumen(db, user))


@router.post("/leer", response_model=FacturaDetalleOut, status_code=201)
async def leer_con_ia(
    archivo: UploadFile = File(...),
    # Las facturas electrónicas suelen venir protegidas (la clave es el NIT del emisor)
    contrasena: str | None = Form(None),
    db: Session = Depends(get_db),
    user: Usuario = Depends(get_current_user),
):
    """Lee un documento con el modelo de visión y lo deja como una factura normal.

    El resultado entra por el **mismo camino** que todo lo demás: se guarda el texto, se revisan
    el monto y la fecha con las reglas de la app (y sus avisos), y el usuario lo confirma o lo
    corrige con las herramientas de siempre.
    """
    contenido = await archivo.read()
    limite = get_settings().tamano_maximo_archivo_mb * 1024 * 1024
    if len(contenido) > limite:
        raise HTTPException(
            status_code=413,
            detail=f"El archivo pesa más de {get_settings().tamano_maximo_archivo_mb} MB.",
        )

    # 1) El cupo se comprueba **antes** de llamar al proveedor: si no hay, no se gasta nada.
    resumen = cuotas.resumen(db, user)
    if resumen["lecturas"]["restantes"] < 1:
        raise cuotas.agotado(cuotas.LECTURA_IA, resumen)

    # 2) La lectura
    try:
        lectura = ia.leer_documento(
            contenido, archivo.filename or "documento", archivo.content_type, contrasena
        )
    except ia.IaNoConfigurada as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail=(
                "El proveedor de IA no pudo leer el documento; no se descontó ninguna lectura "
                f"de tu plan. ({type(error).__name__})"
            ),
        ) from error

    # 3) Se cobra **después** de que salga bien, y se anota lo que costó de verdad
    cuotas.consumir(db, user, cuotas.LECTURA_IA)
    cuotas.registrar_gasto(
        db, user, lectura.tokens_entrada, lectura.tokens_salida, lectura.costo_usd
    )

    # 4) La factura, por el camino de siempre
    campos = lectura.campos
    texto = lectura.texto or ""
    emisor_detectado = detectar_emisor(texto) if texto else None
    monto = campos.get("monto")
    if monto is None:
        monto = detectar_monto(texto) if texto else None
    fecha = None
    if campos.get("fecha"):
        try:
            fecha = hoy().fromisoformat(str(campos["fecha"])[:10])
        except ValueError:
            fecha = None

    factura = Factura(
        usuario_id=user.id,
        nombre_archivo=archivo.filename or "documento",
        texto_extraido=texto[:20000] or None,
        monto_detectado=monto,
        fecha_detectada=fecha,
        emisor=(emisor_detectado[0] if emisor_detectado else None),
        emisor_nombre=(campos.get("emisor") or (emisor_detectado[1] if emisor_detectado else None)),
    )
    db.add(factura)
    db.flush()

    lineas = campos.get("lineas") or []
    if lineas and detectar_tipo(texto, lineas) not in ("parqueadero", "servicios"):
        for orden, fila in enumerate(lineas):
            db.add(
                FacturaLinea(
                    factura_id=factura.id,
                    orden=orden,
                    descripcion=fila["descripcion"],
                    valor_total=fila["valor"],
                    origen="ia",
                )
            )
    db.commit()
    db.refresh(factura)

    from ..routers.facturas import _detalle  # el mismo detalle que ve el resto de la app

    detalle = _detalle(db, factura)
    avisos = []
    if not ia.configurada():
        avisos.append("Leído con IA.")
    aviso_monto = aviso_del_monto(monto, texto)
    aviso_fecha = aviso_de_la_fecha(fecha, hoy())
    detalle.aviso = " ".join(a for a in [aviso_monto, aviso_fecha] if a) or None
    return detalle
