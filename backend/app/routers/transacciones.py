"""CRUD de transacciones (aislado por usuario).

Aquí viven también las reglas de las **transferencias** entre cuentas propias: no
son ingreso ni gasto, así que quedan fuera de los reportes, del flujo de caja y de
los presupuestos, y mueven el saldo de dos cuentas a la vez.

Una transferencia exige que las dos cuentas estén en la **misma moneda**: mover
entre monedas distintas necesita su propia tasa y un segundo importe
(`monto_destino`), que es una tarea aparte.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..crud_utils import get_owned
from ..deps import get_current_user, get_db
from ..facturas import nombre_factura
from ..models import (
    Categoria,
    EstadoSuscripcion,
    Etiqueta,
    Factura,
    FacturaLinea,
    IngresoRecurrente,
    Periodicidad,
    PeriodicidadIngreso,
    Suscripcion,
    TipoTransaccion,
    Transaccion,
    Usuario,
)
from ..movimientos import (
    validar,
    validar_cuentas,
    validar_referencias,
)
from ..recurrencia import hoy, siguiente_ocurrencia, siguiente_pago
from ..schemas import MovimientoOut, TransaccionIn, TransaccionOut, TransaccionUpdate

router = APIRouter(prefix="/transacciones", tags=["transacciones"])

# Periodicidades válidas según el tipo de movimiento (los ENUM no son iguales)
PERIODICIDAD_GASTO = {p.value: p for p in Periodicidad}
PERIODICIDAD_INGRESO = {p.value: p for p in PeriodicidadIngreso}

# Lo que una transferencia **no** puede llevar: no tiene categoría (no es un gasto
# que se clasifique), ni suscripción ni etiqueta.








@router.get("", response_model=list[TransaccionOut])
def listar(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return db.scalars(
        select(Transaccion)
        .where(Transaccion.usuario_id == user.id)
        .order_by(Transaccion.fecha.desc())
    ).all()


def _movimientos(db: Session, user: Usuario) -> list[MovimientoOut]:
    """Agrupa las transacciones de cada compra (factura) en **un** movimiento.

    Una factura de mercado confirmada crea una transacción por artículo (120 filas).
    Aquí se colapsan en una sola fila: el monto es la suma y `articulos` dice cuántos
    hay detrás; el detalle vive en `GET /facturas/{id}/detalle`.
    """
    txs = list(db.scalars(select(Transaccion).where(Transaccion.usuario_id == user.id)).all())
    categorias = {
        c.id: c.nombre for c in db.scalars(select(Categoria).where(Categoria.usuario_id == user.id)).all()
    }
    etiquetas = {
        e.id: (e.nombre, e.categoria_id)
        for e in db.scalars(select(Etiqueta).where(Etiqueta.usuario_id == user.id)).all()
    }
    facturas = list(db.scalars(select(Factura).where(Factura.usuario_id == user.id)).all())

    consumidas: set[uuid.UUID] = set()
    movimientos: list[MovimientoOut] = []

    # 1) Cada factura confirmada es un único movimiento (con sus artículos como detalle).
    for factura in facturas:
        lineas = list(
            db.scalars(select(FacturaLinea).where(FacturaLinea.factura_id == factura.id)).all()
        )
        confirmadas = [li for li in lineas if li.transaccion_id is not None]
        if not confirmadas:
            continue  # sin confirmar: aún no es un movimiento
        ids = sorted({li.transaccion_id for li in confirmadas if li.transaccion_id})
        base = next((db.get(Transaccion, i) for i in ids if i == factura.transaccion_id), None)
        if base is None and ids:
            base = db.get(Transaccion, ids[0])
        total = sum((li.valor_total for li in confirmadas), Decimal("0"))
        ets: list[str] = []
        for li in confirmadas:
            if li.etiqueta_id in etiquetas and etiquetas[li.etiqueta_id][0] not in ets:
                ets.append(etiquetas[li.etiqueta_id][0])
        desc = base.descripcion if base and base.descripcion else nombre_factura(factura.nombre_archivo)
        cat_nombre = categorias.get(base.categoria_id) if base and base.categoria_id else None
        movimientos.append(
            MovimientoOut(
                id=base.id if base else None,
                ids=ids,
                tipo=base.tipo.value if base else "gasto",
                monto=total,
                fecha=factura.fecha_detectada or (base.fecha if base else hoy()),
                descripcion=desc,
                categoria_id=base.categoria_id if base else None,
                categoria=cat_nombre,
                etiqueta_id=base.etiqueta_id if base else None,
                etiquetas=ets,
                factura_id=factura.id,
                articulos=len(confirmadas),
                agrupada=True,
                cuenta_id=base.cuenta_id if base else None,
                tarjeta_id=base.tarjeta_id if base else None,
                moneda=base.moneda if base else "COP",
                notas=base.notas if base else None,
                busqueda=" ".join([desc or "", cat_nombre or "", " ".join(ets)] + [li.descripcion for li in confirmadas]).lower(),
                suscripcion_id=base.suscripcion_id if base else None,
                ingreso_recurrente_id=base.ingreso_recurrente_id if base else None,
                poliza_id=base.poliza_id if base else None,
            )
        )
        consumidas.update(ids)

    # 2) Las transacciones sueltas (sin factura).
    for t in txs:
        if t.id in consumidas:
            continue
        cat_nombre = categorias.get(t.categoria_id) if t.categoria_id else None
        etq_nombre = etiquetas.get(t.etiqueta_id, (None, None))[0] if t.etiqueta_id else None
        movimientos.append(
            MovimientoOut(
                id=t.id,
                ids=[t.id],
                tipo=t.tipo.value,
                monto=t.monto,
                fecha=t.fecha,
                descripcion=t.descripcion,
                categoria_id=t.categoria_id,
                categoria=cat_nombre,
                etiqueta_id=t.etiqueta_id,
                cuenta_id=t.cuenta_id,
                cuenta_destino_id=t.cuenta_destino_id,
                tarjeta_id=t.tarjeta_id,
                moneda=t.moneda,
                notas=t.notas,
                busqueda=" ".join([t.descripcion or "", cat_nombre or "", etq_nombre or ""]).lower(),
                suscripcion_id=t.suscripcion_id,
                ingreso_recurrente_id=t.ingreso_recurrente_id,
                poliza_id=t.poliza_id,
            )
        )

    movimientos.sort(key=lambda m: m.fecha, reverse=True)
    return movimientos


@router.get("/movimientos", response_model=list[MovimientoOut])
def movimientos(db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    """Listado **agrupado**: una compra (factura) es un solo movimiento."""
    return _movimientos(db, user)


def _crear_compromiso(db: Session, user: Usuario, datos: dict, periodicidad: str) -> dict:
    """Crea el compromiso recurrente y devuelve el enlace para la transacción.

    La transacción que se está creando es el pago de **este** periodo, así que el
    compromiso queda apuntando al **siguiente**: el job no duplica el de ahora.

    El día sale de la fecha del movimiento (día del mes o de la semana), y el
    nombre, el monto, la categoría, la etiqueta, la cuenta y la tarjeta se heredan
    del propio movimiento: no hay que teclear nada dos veces.
    """
    tipo = datos["tipo"]
    fecha = datos["fecha"]
    nombre = (datos.get("descripcion") or "").strip() or "Movimiento recurrente"

    if tipo == TipoTransaccion.TRANSFERENCIA:
        raise HTTPException(
            status_code=422,
            detail=(
                "Una transferencia no puede ser recurrente todavía: el compromiso "
                "tiene que saber de qué cuenta sale y a cuál entra en cada periodo"
            ),
        )

    if tipo == TipoTransaccion.GASTO:
        if periodicidad not in PERIODICIDAD_GASTO:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"«{periodicidad}» no vale para un gasto recurrente; usa una de "
                    f"{', '.join(PERIODICIDAD_GASTO)}"
                ),
            )
        per = PERIODICIDAD_GASTO[periodicidad]
        compromiso = Suscripcion(
            usuario_id=user.id,
            nombre=nombre,
            monto=datos["monto"],
            moneda=datos["moneda"],
            periodicidad=per,
            fecha_inicio=fecha,
            proximo_pago=siguiente_pago(per, fecha),
            categoria_id=datos.get("categoria_id"),
            etiqueta_id=datos.get("etiqueta_id"),
            tarjeta_id=datos.get("tarjeta_id"),
            cuenta_id=datos.get("cuenta_id"),
            estado=EstadoSuscripcion.ACTIVA,
            notas="Creado desde una transacción",
        )
        db.add(compromiso)
        db.flush()
        return {"suscripcion_id": compromiso.id}

    if periodicidad not in PERIODICIDAD_INGRESO:
        raise HTTPException(
            status_code=422,
            detail=(
                f"«{periodicidad}» no vale para un ingreso recurrente; usa una de "
                f"{', '.join(PERIODICIDAD_INGRESO)}"
            ),
        )
    per_i = PERIODICIDAD_INGRESO[periodicidad]
    dia = None
    if per_i == PeriodicidadIngreso.SEMANAL:
        dia = fecha.weekday()
    elif per_i == PeriodicidadIngreso.MENSUAL:
        dia = fecha.day
    compromiso = IngresoRecurrente(
        usuario_id=user.id,
        nombre=nombre,
        monto=datos["monto"],
        moneda=datos["moneda"],
        periodicidad=per_i,
        dia=dia,
        proxima_ejecucion=siguiente_ocurrencia(per_i, dia, fecha),
        categoria_id=datos.get("categoria_id"),
        cuenta_id=datos.get("cuenta_id"),
    )
    db.add(compromiso)
    db.flush()
    return {"ingreso_recurrente_id": compromiso.id}


@router.post("", response_model=TransaccionOut, status_code=201)
def crear(data: TransaccionIn, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    datos = data.model_dump()
    recurrencia = datos.pop("recurrencia", None)
    validar(datos)
    validar_cuentas(db, user, datos)
    validar_referencias(db, user, datos)

    if recurrencia is not None:
        # Atómico: el movimiento y el compromiso se guardan juntos o no se guarda nada
        datos.update(_crear_compromiso(db, user, datos, recurrencia["periodicidad"]))

    obj = Transaccion(usuario_id=user.id, **datos)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{id}", response_model=TransaccionOut)
def obtener(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    return get_owned(db, Transaccion, id, user.id)


@router.patch("/{id}", response_model=TransaccionOut)
def actualizar(id: uuid.UUID, data: TransaccionUpdate, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Transaccion, id, user.id)
    campos = data.model_dump(exclude_unset=True)

    # Se valida el estado **resultante**, no solo lo que llega: al convertir un
    # movimiento en transferencia hay que mirar también lo que ya tenía guardado.
    resultante = {
        campo: getattr(obj, campo)
        for campo in (
            "tipo", "cuenta_id", "cuenta_destino_id", "categoria_id", "tarjeta_id",
            "suscripcion_id", "ingreso_recurrente_id", "etiqueta_id",
        )
    }
    resultante.update(campos)
    validar(resultante)
    validar_cuentas(db, user, resultante)
    validar_referencias(db, user, resultante)

    for campo, valor in campos.items():
        setattr(obj, campo, valor)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{id}", status_code=204)
def eliminar(id: uuid.UUID, db: Session = Depends(get_db), user: Usuario = Depends(get_current_user)):
    obj = get_owned(db, Transaccion, id, user.id)
    db.delete(obj)
    db.commit()
