"""Guardar y borrar los archivos de las facturas, según lo que incluya el plan.

El archivo se guarda para poder **releerlo con IA** cuando el lector normal falla, y se borra
solo al cumplirse la retención. Si el usuario llegó a su límite, la factura se sube igual (el
texto y el monto se leen de una vez): lo único que no habrá es la relectura con IA.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import almacen
from .config import get_settings
from .db import make_engine, make_session_factory
from .models import Factura, Plan, Usuario
from .recurrencia import hoy

# Lo que se guarda si el usuario no tiene plan (o el plan no lo dice)
ARCHIVOS_POR_DEFECTO = 30
RETENCION_POR_DEFECTO = 7
MB_POR_DEFECTO = 60


def plan_de(db: Session, usuario: Usuario) -> Plan | None:
    return db.get(Plan, usuario.plan_codigo) if usuario.plan_codigo else None


def limites(db: Session, usuario: Usuario) -> tuple[int | None, int, int]:
    """(archivos incluidos —None es ilimitado—, días de retención, MB incluidos)."""
    plan = plan_de(db, usuario)
    if plan is None:
        return ARCHIVOS_POR_DEFECTO, RETENCION_POR_DEFECTO, MB_POR_DEFECTO
    return (
        plan.archivos_incluidos,
        plan.retencion_dias or RETENCION_POR_DEFECTO,
        plan.almacenamiento_mb or MB_POR_DEFECTO,
    )


def uso(db: Session, usuario: Usuario) -> tuple[int, int]:
    """Cuántos archivos guardados tiene y cuánto pesan (bytes)."""
    fila = db.execute(
        select(
            func.count().label("archivos"),
            func.coalesce(func.sum(Factura.archivo_bytes), 0).label("bytes"),
        ).where(Factura.usuario_id == usuario.id, Factura.archivo_clave.is_not(None))
    ).one()
    return int(fila.archivos), int(fila.bytes)


def _peso(mb: float) -> str:
    """El peso como se lee bien: 2,0 MB · 45,3 MB · 500 MB · 1 GB."""
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB".replace(".0 GB", " GB")
    if mb < 100:
        return f"{mb:.1f} MB".replace(".", ",")
    return f"{mb:,.0f} MB".replace(",", ".")


def hay_sitio(db: Session, usuario: Usuario, nuevos_bytes: int) -> tuple[bool, str]:
    """¿Cabe otro archivo? Devuelve (sí/no, motivo para el usuario).

    El motivo se le da al usuario tal cual, así que dice **cuánto lleva** y **qué puede hacer**:
    borrar alguno, esperar a que se borren solos (la retención) o subir de plan.
    """
    incluidos, dias, mb = limites(db, usuario)
    archivos, bytes_usados = uso(db, usuario)
    usados_mb = bytes_usados / 1024 / 1024
    if incluidos is not None and archivos >= incluidos:
        return False, (
            f"Tu plan guarda {incluidos} archivos a la vez y ya los tienes. Puedes borrar el de "
            f"una factura que ya registraste, esperar a que se borren solos ({dias} días) o subir "
            "de plan."
        )
    if bytes_usados + nuevos_bytes > mb * 1024 * 1024:
        return False, (
            f"Ya usas {_peso(usados_mb)} de los {_peso(mb)} que guarda tu plan. Puedes borrar "
            f"algún archivo, esperar a que se borren solos ({dias} días) o subir de plan."
        )
    return True, ""


def guardar_factura(
    db: Session,
    factura: Factura,
    usuario: Usuario,
    contenido: bytes,
    tipo: str | None,
) -> tuple[bool, str]:
    """Guarda el archivo de una factura recién subida, si el plan lo permite.

    Devuelve (guardado, motivo). Nunca falla la subida por esto: el archivo es un extra para
    poder releer, no un requisito para registrar el gasto.
    """
    cabe, motivo = hay_sitio(db, usuario, len(contenido))
    if not cabe:
        return False, motivo

    _incluidos, dias, _mb = limites(db, usuario)
    clave = almacen.clave_de(usuario.id, factura.id, factura.nombre_archivo)
    try:
        factura.archivo_bytes = almacen.guardar(clave, contenido)
    except OSError as error:  # disco lleno, permisos…: se dice y la factura sigue su curso
        return False, f"No pudimos guardar el archivo para releerlo después ({error.strerror})."
    factura.archivo_clave = clave
    factura.archivo_tipo = tipo
    factura.archivo_expira_en = datetime.now(UTC) + timedelta(days=dias)
    db.flush()
    return True, ""


def borrar_archivo(db: Session, factura: Factura) -> None:
    """Borra el archivo de una factura (el usuario lo pide, o venció la retención)."""
    if factura.archivo_clave:
        almacen.borrar(factura.archivo_clave)
    factura.archivo_clave = None
    factura.archivo_tipo = None
    factura.archivo_bytes = None
    factura.archivo_expira_en = None


def contenido_de(factura: Factura, contrasena: str | None = None) -> bytes:
    """El archivo guardado de una factura, o un error que explica qué pasó."""
    if not factura.archivo_clave:
        raise HTTPException(
            status_code=409,
            detail=(
                "No tenemos el archivo de esta factura: llegaste al límite de tu plan o ya se "
                "cumplió el tiempo de retención. Vuelve a subir el documento si quieres leerlo "
                "con IA."
            ),
        )
    try:
        return almacen.leer(factura.archivo_clave)
    except almacen.ArchivoNoEncontrado as error:
        raise HTTPException(status_code=410, detail=str(error)) from error


def resumen(db: Session, usuario: Usuario) -> dict:
    """Lo que el usuario lleva de almacenamiento: la foto de ahora y lo medido en el mes.

    La foto dice cuántos archivos tiene; el **MB-día** dice cuánto espacio ha ocupado de verdad
    a lo largo del mes, que es lo que se cobra y lo que se promedia.
    """
    incluidos, dias, mb = limites(db, usuario)
    archivos, bytes_usados = uso(db, usuario)
    return {
        "archivos_usados": archivos,
        "archivos_incluidos": incluidos,  # None = ilimitado
        "mb_usados": round(bytes_usados / 1024 / 1024, 3),
        "mb_incluidos": mb,
        "retencion_dias": dias,
        **promedio(db, usuario),
    }


def borrar_archivos_vencidos(s: Session) -> int:
    """Borra los archivos cuya retención se cumplió. La factura se queda: solo pierde el archivo."""
    ahora = datetime.now(UTC)
    vencidas = s.scalars(
        select(Factura).where(
            Factura.archivo_clave.is_not(None),
            Factura.archivo_expira_en.is_not(None),
            Factura.archivo_expira_en <= ahora,
        )
    ).all()
    for factura in vencidas:
        borrar_archivo(s, factura)
    return len(vencidas)


def medir_almacenamiento(s: Session, cuando: date | None = None) -> int:
    """Suma al mes en curso lo que ocupan los archivos de cada usuario. Una vez por día.

    Es la parte que permite cobrar el espacio con criterio: 30 archivos guardados una semana no
    pesan lo mismo que 30 guardados un mes. Se puede llamar varias veces al día: la segunda no
    cuenta (queda anotado el último día medido).
    """
    from .models import ConsumoIa

    hoy_ = cuando or hoy()
    periodo = hoy_.strftime("%Y-%m")
    medidos = 0
    usuarios = s.scalars(
        select(Usuario).where(
            select(Factura.id)
            .where(Factura.usuario_id == Usuario.id, Factura.archivo_clave.is_not(None))
            .exists()
        )
    ).all()
    for usuario in usuarios:
        archivos, bytes_usados = uso(s, usuario)
        fila = s.scalar(
            select(ConsumoIa).where(
                ConsumoIa.usuario_id == usuario.id, ConsumoIa.periodo == periodo
            )
        )
        if fila is None:
            fila = ConsumoIa(usuario_id=usuario.id, periodo=periodo)
            s.add(fila)
            s.flush()
        if fila.ultima_medicion == hoy_:
            continue  # ya se midió hoy: no se cuenta dos veces
        fila.archivos_dia += archivos
        fila.mb_dia = Decimal(str(fila.mb_dia or 0)) + Decimal(str(round(bytes_usados / 1024 / 1024, 3)))
        fila.dias_medidos += 1
        fila.ultima_medicion = hoy_
        medidos += 1
    return medidos


def medir_almacenamiento_diario() -> int:
    """Trabajo programado: mide el almacenamiento de todos los usuarios una vez al día."""
    engine = make_engine()
    sf = make_session_factory(engine)
    try:
        with sf.begin() as s:
            return medir_almacenamiento(s)
    finally:
        engine.dispose()


def promedio(s: Session, usuario: Usuario) -> dict:
    """El promedio diario del mes: es lo que se compara contra el plan."""
    from .models import ConsumoIa

    fila = s.scalar(
        select(ConsumoIa).where(
            ConsumoIa.usuario_id == usuario.id, ConsumoIa.periodo == periodo_actual()
        )
    )
    if fila is None or not fila.dias_medidos:
        return {"archivos_promedio": 0.0, "mb_promedio": 0.0, "mb_dia": 0.0, "dias_medidos": 0}
    dias = fila.dias_medidos
    return {
        "archivos_promedio": round(fila.archivos_dia / dias, 2),
        "mb_promedio": round(float(fila.mb_dia) / dias, 3),
        "mb_dia": float(fila.mb_dia),
        "dias_medidos": dias,
    }


def periodo_actual() -> str:
    return hoy().strftime("%Y-%m")


def borrar_huerfanos(s: Session) -> int:
    """Borra del almacén lo que ya no referencia ninguna factura.

    Pasa cuando se borra un usuario (o una factura) por fuera de la app, o si algo falla a mitad:
    quedan archivos que nadie puede borrar desde la pantalla y que se van acumulando. La base manda:
    lo que no esté referenciado, fuera.
    """
    raiz = Path(get_settings().almacen_ruta)
    if not raiz.is_dir():
        return 0
    referenciadas = {
        clave
        for clave in s.scalars(select(Factura.archivo_clave).where(Factura.archivo_clave.is_not(None)))
    }
    borrados = 0
    for ruta in raiz.rglob("*"):
        if not ruta.is_file():
            continue
        clave = str(ruta.relative_to(raiz))
        if clave in referenciadas:
            continue
        ruta.unlink(missing_ok=True)
        borrados += 1
        # si era el último de su carpeta, la carpeta se va también
        padre = ruta.parent
        if padre != raiz and padre.is_dir() and not any(padre.iterdir()):
            padre.rmdir()
    return borrados


def limpiar_archivos_vencidos() -> int:
    """Trabajo programado: borra lo vencido y lo que ya no referencia nadie."""
    engine = make_engine()
    sf = make_session_factory(engine)
    try:
        with sf.begin() as s:
            vencidos = borrar_archivos_vencidos(s)
            huerfanos = borrar_huerfanos(s)
            return vencidos + huerfanos
    finally:
        engine.dispose()
