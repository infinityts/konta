"""Informe del mes: cuánto cuesta de verdad cada plan y qué margen deja.

Es la pieza que permite poner precios con datos en vez de a ojo. Junta lo que ya se mide —lecturas
con IA, consultas, tokens, coste facturado por el proveedor y MB-día de almacenamiento— y lo
compara con lo que pagan los clientes.

Se informan **promedios y percentiles (p50 y p90)**: el promedio solo dice la mitad de la
historia, y el p90 es el que enseña cuánto cuesta el 10 % que más usa la app.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import ConsumoIa, Pago, Plan, Usuario
from .recurrencia import hoy
from .tasas import convertir


def es_admin(usuario: Usuario) -> bool:
    """Solo los correos configurados pueden ver el informe de todos los clientes."""
    admins = [c.strip().lower() for c in (get_settings().informe_admins or "").split(",") if c.strip()]
    return bool(admins) and (usuario.email or "").lower() in admins


def _percentil(valores: list[float], q: float) -> float:
    """Percentil con interpolación lineal, como hace Postgres con percentile_cont."""
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    if len(ordenados) == 1:
        return round(ordenados[0], 4)
    posicion = q * (len(ordenados) - 1)
    abajo = int(posicion)
    arriba = min(abajo + 1, len(ordenados) - 1)
    peso = posicion - abajo
    return round(ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * peso, 4)


def _resumen_de(valores: list[float]) -> dict:
    if not valores:
        return {"total": 0.0, "promedio": 0.0, "p50": 0.0, "p90": 0.0, "max": 0.0}
    return {
        "total": round(sum(valores), 4),
        "promedio": round(sum(valores) / len(valores), 4),
        "p50": _percentil(valores, 0.5),
        "p90": _percentil(valores, 0.9),
        "max": round(max(valores), 4),
    }


UMBRAL_AJUSTADO = 0.6  # a partir de aquí, el cliente se está comiendo el margen


# Cuántos clientes se devuelven en el detalle. Con miles de clientes, traerlos todos sería una
# consulta pesada que nadie va a leer entera: se devuelven los que peor van (que son los que se
# vienen a mirar) y se dice cuántos quedaron fuera.
LIMITE_POR_USUARIO = 500


def informe_por_usuario(db: Session, periodo: str | None = None, limite: int | None = None) -> dict:
    """Cliente por cliente: lo que paga contra lo que cuesta, y quién se está pasando.

    Es la parte que no se ve a simple vista: un plan puede dejar margen de sobra **en promedio** y
    tener dentro un cliente que cuesta más de lo que paga. Aquí salen los dos casos que hay que
    mirar: `pierde` (cuesta más de lo que paga) y `ajustado` (se come más del 60 % del precio).
    """
    periodo = periodo or hoy().strftime("%Y-%m")
    admins = {c.strip().lower() for c in (get_settings().informe_admins or "").split(",") if c.strip()}
    usuarios = {
        u.id: u for u in db.scalars(select(Usuario)).all() if (u.email or "").lower() not in admins
    }
    planes = {p.codigo: p for p in db.scalars(select(Plan)).all()}
    consumos = {
        c.usuario_id: c for c in db.scalars(select(ConsumoIa).where(ConsumoIa.periodo == periodo))
    }

    trm = convertir(db, "USD", "COP", Decimal("1"))
    cop_por_usd = float(trm) if trm else None
    precio_gb = get_settings().costo_gb_mes_usd

    filas = []
    sin_plan = []
    for usuario in usuarios.values():
        plan = planes.get(usuario.plan_codigo or "")
        if plan is None:
            # No se esconde: se cuenta con el plan base (que es lo que la app le aplica) y se dice
            sin_plan.append(usuario.email)
            plan = planes.get(get_settings().plan_base or "basico")
            if plan is None:
                continue
        consumo = consumos.get(usuario.id)
        costo_ia_usd = float(consumo.costo_usd or 0) if consumo else 0.0
        mb_dia = float(consumo.mb_dia or 0) if consumo else 0.0
        costo_almacen_usd = (mb_dia / 1024) * precio_gb if precio_gb else 0.0
        costo_total_usd = costo_ia_usd + costo_almacen_usd
        costo_cop = costo_total_usd * cop_por_usd if cop_por_usd else None
        precio = float(plan.precio_mes)
        margen = (precio - costo_cop) if costo_cop is not None else None

        if costo_cop is None:
            aviso = None
        elif costo_cop > precio:
            aviso = "pierde"
        elif costo_cop > precio * UMBRAL_AJUSTADO:
            aviso = "ajustado"
        else:
            aviso = None

        filas.append(
            {
                "usuario": usuario.email,
                "plan": plan.codigo,
                "precio_mes": precio,
                "lecturas": int(consumo.lecturas or 0) if consumo else 0,
                "consultas": int(consumo.consultas or 0) if consumo else 0,
                "tokens_entrada": int(consumo.tokens_entrada or 0) if consumo else 0,
                "tokens_salida": int(consumo.tokens_salida or 0) if consumo else 0,
                "mb_dia": round(mb_dia, 3),
                "costo_ia_usd": round(costo_ia_usd, 6),
                "costo_almacen_usd": round(costo_almacen_usd, 6) if precio_gb else None,
                "costo_total_cop": round(costo_cop, 2) if costo_cop is not None else None,
                "margen_cop": round(margen, 2) if margen is not None else None,
                "margen_pct": round(100 * margen / precio, 2) if (margen is not None and precio) else None,
                "aviso": aviso,
            }
        )

    # Los que peor van, primero: es lo que se viene a mirar
    filas.sort(key=lambda f: (f["margen_pct"] if f["margen_pct"] is not None else 100))

    alertas = [f for f in filas if f["aviso"]]
    tope = limite or LIMITE_POR_USUARIO
    total = len(filas)
    filas = filas[:tope]
    return {
        "periodo": periodo,
        "clientes": total,
        "mostrados": len(filas),
        "nota_limite": (
            f"Se muestran los {tope} que peor van de {total}. El resto va mejor."
            if total > tope
            else None
        ),
        "cop_por_usd": round(cop_por_usd, 2) if cop_por_usd else None,
        "umbral_ajustado": UMBRAL_AJUSTADO,
        "planes_inexistentes": sin_plan,
        "usuarios": filas,
        "alertas": {
            "pierden": [f["usuario"] for f in alertas if f["aviso"] == "pierde"],
            "ajustados": [f["usuario"] for f in alertas if f["aviso"] == "ajustado"],
        },
        "notas": (
            []
            if cop_por_usd
            else ["No hay tasa USD→COP cargada, así que el margen no se puede calcular en pesos."]
        )
        + (
            []
            if precio_gb
            else ["Sin precio por GB-mes el almacenamiento se informa en volumen, no en dinero."]
        )
        + (
            [
                f"{len(sin_plan)} cliente(s) tenían un plan que ya no está en el catálogo "
                f"({', '.join(sin_plan[:5])}): se les aplica el plan base."
            ]
            if sin_plan
            else []
        ),
    }


def informe_del_mes(db: Session, periodo: str | None = None) -> dict:
    """Las cifras del mes por plan, con promedios, percentiles y margen."""
    periodo = periodo or hoy().strftime("%Y-%m")

    # Las cuentas del dueño no son clientes: no se pagan a sí mismas. Si contaran, el informe
    # mostraría ingresos que no existen.
    admins = {c.strip().lower() for c in (get_settings().informe_admins or "").split(",") if c.strip()}
    usuarios = {
        u.id: u for u in db.scalars(select(Usuario)).all() if (u.email or "").lower() not in admins
    }
    cuentas_del_dueno = db.scalar(select(func.count()).select_from(Usuario)) - len(usuarios)
    planes = {p.codigo: p for p in db.scalars(select(Plan)).all()}
    consumos = db.scalars(select(ConsumoIa).where(ConsumoIa.periodo == periodo)).all()

    por_plan: dict[str, dict] = {}
    for codigo, plan in planes.items():
        por_plan[codigo] = {
            "codigo": codigo,
            "nombre": plan.nombre,
            "precio_mes": float(plan.precio_mes),
            "usuarios": 0,
            "lecturas": [],
            "consultas": [],
            "tokens_entrada": [],
            "tokens_salida": [],
            "costo_usd": [],
            "mb_dia": [],
            "archivos_dia": [],
            "dias_medidos": [],
        }

    # Los usuarios sin consumo también cuentan: pagan y no gastan
    for usuario in usuarios.values():
        codigo = usuario.plan_codigo if usuario.plan_codigo in por_plan else None
        if codigo:
            por_plan[codigo]["usuarios"] += 1

    for consumo in consumos:
        usuario = usuarios.get(consumo.usuario_id)
        codigo = (usuario.plan_codigo if usuario else None) or None
        if codigo not in por_plan:
            continue
        fila = por_plan[codigo]
        fila["lecturas"].append(float(consumo.lecturas or 0))
        fila["consultas"].append(float(consumo.consultas or 0))
        fila["tokens_entrada"].append(float(consumo.tokens_entrada or 0))
        fila["tokens_salida"].append(float(consumo.tokens_salida or 0))
        fila["costo_usd"].append(float(consumo.costo_usd or 0))
        fila["mb_dia"].append(float(consumo.mb_dia or 0))
        fila["archivos_dia"].append(float(consumo.archivos_dia or 0))
        fila["dias_medidos"].append(int(consumo.dias_medidos or 0))

    # Lo que **de verdad** entró este mes: los pagos cobrados. El precio del plan por sus clientes
    # es lo que se esperaría cobrar cada mes, y no es lo mismo: alguien puede haber comprado a
    # mitad de mes, o haber cambiado de plan. Mezclarlas sería mentir en el informe del dinero.
    cobrado = float(
        db.scalar(
            select(func.coalesce(func.sum(Pago.monto), 0)).where(
                Pago.estado == "pagado",
                # El mes del pago contado como lo vive el usuario (Colombia). Con la hora
                # UTC, un pago de las 19:30 del último día del mes caía en el mes siguiente.
                func.to_char(func.timezone(get_settings().timezone, Pago.pagado_en), "YYYY-MM")
                == periodo,
            )
        )
        or 0
    )
    cobrado_por_plan: dict[str, float] = {}
    for codigo, total in db.execute(
        select(Pago.codigo, func.coalesce(func.sum(Pago.monto), 0))
        .where(
            Pago.estado == "pagado",
            Pago.tipo == "plan",
            func.to_char(func.timezone(get_settings().timezone, Pago.pagado_en), "YYYY-MM")
            == periodo,
        )
        .group_by(Pago.codigo)
    ).all():
        cobrado_por_plan[codigo] = float(total)

    # A cuánto está el dólar hoy, para poder comparar contra el precio en pesos
    trm = convertir(db, "USD", "COP", Decimal("1"))
    cop_por_usd = float(trm) if trm else None

    precio_gb = get_settings().costo_gb_mes_usd
    planes_salida = []
    totales = {
        "usuarios": 0,
        "ingreso_cop": 0.0,
        "costo_ia_usd": 0.0,
        "mb_dia": 0.0,
        "lecturas": 0.0,
        "consultas": 0.0,
    }
    for fila in por_plan.values():
        usuarios_plan = fila["usuarios"]
        ingreso = fila["precio_mes"] * usuarios_plan
        costo_ia_usd = sum(fila["costo_usd"])
        mb_dia = sum(fila["mb_dia"])
        gb_mes = mb_dia / 1024
        costo_almacen_usd = gb_mes * precio_gb if precio_gb else 0.0
        costo_total_usd = costo_ia_usd + costo_almacen_usd
        costo_cop = costo_total_usd * cop_por_usd if cop_por_usd else None
        margen = (ingreso - costo_cop) if (costo_cop is not None and ingreso) else None

        planes_salida.append(
            {
                "codigo": fila["codigo"],
                "nombre": fila["nombre"],
                "precio_mes": fila["precio_mes"],
                "usuarios": usuarios_plan,
                "ingreso_cop": round(ingreso, 2),
                "cobrado_cop": round(cobrado_por_plan.get(fila["codigo"], 0.0), 2),
                "lecturas": _resumen_de(fila["lecturas"]),
                "consultas": _resumen_de(fila["consultas"]),
                "tokens_entrada": _resumen_de(fila["tokens_entrada"]),
                "tokens_salida": _resumen_de(fila["tokens_salida"]),
                "costo_ia": _resumen_de(fila["costo_usd"]),
                "mb_dia": _resumen_de(fila["mb_dia"]),
        "archivos_promedio": round(
            sum(fila["archivos_dia"]) / sum(fila["dias_medidos"]) if sum(fila["dias_medidos"]) else 0,
            2,
        ),
        "tamano_medio_archivo_mb": round(
            sum(fila["mb_dia"]) / sum(fila["archivos_dia"]) if sum(fila["archivos_dia"]) else 0, 3
        ),
                "gb_mes": round(gb_mes, 4),
                "costo_ia_usd": round(costo_ia_usd, 6),
                "costo_almacen_usd": round(costo_almacen_usd, 6) if precio_gb else None,
                "costo_total_cop": round(costo_cop, 2) if costo_cop is not None else None,
                "margen_cop": round(margen, 2) if margen is not None else None,
                "margen_pct": round(100 * margen / ingreso, 2) if (margen is not None and ingreso) else None,
            }
        )
        totales["usuarios"] += usuarios_plan
        totales["ingreso_cop"] += ingreso
        totales["costo_ia_usd"] += costo_ia_usd
        totales["mb_dia"] += mb_dia
        totales["lecturas"] += sum(fila["lecturas"])
        totales["consultas"] += sum(fila["consultas"])

    notas = []
    if not precio_gb:
        notas.append(
            "El coste del almacenamiento no se convierte a dinero porque falta el precio por "
            "GB-mes (FINANZAS_COSTO_GB_MES_USD). Se informa el volumen consumido."
        )
    if not cop_por_usd:
        notas.append(
            "No hay tasa USD→COP cargada, así que el margen no se puede calcular en pesos."
        )
    if not consumos:
        notas.append("Todavía no hay consumo registrado en este periodo.")
    if cuentas_del_dueno:
        notas.append(
            f"{cuentas_del_dueno} cuenta(s) del dueño quedaron fuera del informe: no son clientes."
        )

    return {
        "periodo": periodo,
        "dias_del_mes": hoy().day,
        "cuentas_del_dueno_excluidas": cuentas_del_dueno,
        "usuarios": totales["usuarios"],
        # Dos cifras distintas, cada una con su nombre: lo cobrado este mes y lo que se esperaría
        # cobrar cada mes con los planes que hay.
        "cobrado_cop": round(cobrado, 2),
        "ingreso_cop": round(totales["ingreso_cop"], 2),
        "costo_ia_usd": round(totales["costo_ia_usd"], 6),
        "costo_ia_cop": round(totales["costo_ia_usd"] * cop_por_usd, 2) if cop_por_usd else None,
        "mb_dia": round(totales["mb_dia"], 3),
        "gb_mes": round(totales["mb_dia"] / 1024, 4),
        "cop_por_usd": round(cop_por_usd, 2) if cop_por_usd else None,
        "planes": sorted(planes_salida, key=lambda p: p["precio_mes"]),
        "notas": notas,
    }
