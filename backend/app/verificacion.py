"""Comprobar que una copia de la base tiene **los mismos números** que el original.

Es la prueba que decide si una migración salió bien: no basta con que las tablas existan ni con
que los usuarios estén; lo que tiene que cuadrar es la **plata**. Por eso no se cuentan solo filas:
también se suman los montos y se saca una **huella** (md5) del contenido de las tablas que llevan
dinero, que delata un monto cambiado aunque el número de filas sea el mismo.

Se usa desde `scripts/verificar_migracion.py`, y sirve igual para comparar producción con la copia
restaurada en la máquina nueva.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from .saldos import saldo_cuentas

# Tablas que llevan dinero o de las que cuelga todo lo demás
TABLAS = (
    "usuarios",
    "cuentas",
    "categorias",
    "etiquetas",
    "transacciones",
    "tarjetas",
    "suscripciones",
    "ingresos_recurrentes",
    "polizas",
    "presupuestos",
    "metas",
    "facturas",
    "facturas_lineas",
    "consumos_ia",
    "pagos",
    "propuestas",
    "consultas_asistente",
)

# Huellas: la lista de columnas de cada tabla, en orden (delata un dato cambiado, no solo uno que
# falte). Se calculan en la base para no traerse las filas.
HUELLAS = {
    "transacciones": "fecha, monto, tipo, coalesce(descripcion, '')",
    "facturas": "coalesce(monto_detectado, 0), coalesce(fecha_detectada, date '1900-01-01'), nombre_archivo",
    "cuentas": "nombre, saldo_inicial, moneda",
    "pagos": "referencia, monto, estado, aplicado",
    "consumos_ia": "periodo, lecturas, consultas, tokens_entrada, tokens_salida, costo_usd, mb_dia",
}


def resumen_de(db: Session) -> dict:
    """Los números que tienen que cuadrar en cualquier copia de esta base."""
    resumen: dict = {"tablas": {}, "dinero": {}, "huellas": {}, "saldos": {}}

    for tabla in TABLAS:
        existe = db.scalar(
            text("select to_regclass(:t) is not null"), {"t": f"public.{tabla}"}
        )
        if not existe:
            continue
        resumen["tablas"][tabla] = int(db.scalar(text(f"select count(*) from {tabla}")) or 0)

    filas = db.execute(
        text(
            "select tipo::text, count(*), coalesce(sum(monto), 0) "
            "from transacciones group by tipo order by tipo"
        )
    ).all()
    resumen["dinero"]["transacciones_por_tipo"] = {
        tipo: {"filas": int(n), "total": float(total)} for tipo, n, total in filas
    }
    resumen["dinero"]["total_ingresos"] = float(
        db.scalar(text("select coalesce(sum(monto), 0) from transacciones where tipo = 'ingreso'")) or 0
    )
    resumen["dinero"]["total_gastos"] = float(
        db.scalar(text("select coalesce(sum(monto), 0) from transacciones where tipo = 'gasto'")) or 0
    )
    resumen["dinero"]["iva_facturas"] = float(
        db.scalar(text("select coalesce(sum(iva_valor), 0) from facturas where iva_valor is not null")) or 0
    )
    resumen["dinero"]["lecturas_ia"] = int(
        db.scalar(text("select coalesce(sum(lecturas), 0) from consumos_ia")) or 0
    )

    for tabla, columnas in HUELLAS.items():
        if tabla not in resumen["tablas"]:
            continue
        # concat_ws une las columnas de cada fila; string_agg las une todas, en orden estable
        fila = f"concat_ws('|', {columnas})"
        huella = db.scalar(
            text(
                f"select md5(coalesce(string_agg({fila}, '||' order by {fila}), '')) from {tabla}"
            )
        )
        resumen["huellas"][tabla] = huella

    # El saldo de cada usuario es la cifra que el usuario mira: si esto no cuadra, la migración no
    # terminó bien aunque las tablas estén todas.
    saldos = {}
    for (usuario_id,) in db.execute(text("select id from usuarios order by email")).all():
        datos = saldo_cuentas(db, usuario_id) or {}
        saldos[str(usuario_id)] = round(float(datos.get("saldo_total") or 0), 2)
    resumen["saldos"] = saldos
    return resumen


def comparar(original: dict, copia: dict) -> list[str]:
    """Qué no cuadra entre las dos. Lista vacía = la copia es fiel."""
    problemas: list[str] = []

    for tabla, filas in (original.get("tablas") or {}).items():
        en_copia = (copia.get("tablas") or {}).get(tabla)
        if en_copia is None:
            problemas.append(f"Falta la tabla {tabla} en la copia")
        elif en_copia != filas:
            problemas.append(f"{tabla}: {filas} filas en el original, {en_copia} en la copia")

    for clave, valor in (original.get("dinero") or {}).items():
        en_copia = (copia.get("dinero") or {}).get(clave)
        if en_copia != valor:
            problemas.append(f"{clave}: {valor} en el original, {en_copia} en la copia")

    for tabla, huella in (original.get("huellas") or {}).items():
        en_copia = (copia.get("huellas") or {}).get(tabla)
        if en_copia != huella:
            problemas.append(
                f"{tabla}: los datos no son idénticos (huella distinta) — puede haber un monto "
                "cambiado aunque el número de filas coincida"
            )

    for usuario_id, saldo in (original.get("saldos") or {}).items():
        en_copia = (copia.get("saldos") or {}).get(usuario_id)
        if en_copia is None:
            problemas.append(f"El usuario {usuario_id} no está en la copia")
        elif abs(float(en_copia) - float(saldo)) > 0.01:
            problemas.append(
                f"El saldo del usuario {usuario_id} no cuadra: {saldo} en el original, {en_copia} "
                "en la copia"
            )

    return problemas
