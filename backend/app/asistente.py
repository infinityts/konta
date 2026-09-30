"""El asistente de Konta: responde sobre la app **con las reglas de la app**.

La regla que lo hace fiable: el modelo **no sabe los números**. Pide datos por herramientas que
llaman a los mismos servicios que usan las pantallas (`reportes.panel`, `saldos.saldo_cuenta`,
`reportes.reporte_categorias`…), así que lo que responde coincide con lo que el usuario ve. Si un
dato no está en ninguna herramienta, lo dice; no lo estima.

Es de **solo lectura**: no cambia nada. Cuando el usuario pida registrar o etiquetar, se le
explica dónde se hace (las acciones con confirmación son otra fase).
"""

from __future__ import annotations

import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import cuotas, ia, manual, propuestas
from .models import (
    Categoria,
    ConsultaAsistente,
    Factura,
    Presupuesto,
    Tarjeta,
    TipoTransaccion,
    Transaccion,
    Usuario,
)
from .recurrencia import hoy
from .reportes import panel as reporte_panel
from .reportes import reporte_categorias, reporte_mensual
from .saldos import saldo_cuentas

MAX_VUELTAS = 4
MAX_FILAS = 25

SISTEMA = """Eres el asistente de Konta, una app colombiana de finanzas personales.

Reglas que no puedes romper:
1. Los números salen SIEMPRE de las herramientas. Nunca calcules, estimes ni recuerdes cifras.
2. Si el dato no está en lo que devolvió una herramienta, di que no lo tienes. No lo inventes.
3. No cambias nada por tu cuenta. Puedes **proponer** acciones con la herramienta `proponer`
   (registrar un movimiento o etiquetar uno existente): quedan pendientes y **el usuario las
   confirma en la pantalla**. Nunca digas que algo ya quedó hecho: di que está propuesto y que
   falta su confirmación. Si te falta el monto o la fecha, pregúntalos antes de proponer.
4. Responde corto y claro, en el idioma del usuario, con los montos en pesos colombianos.
5. Si te preguntan cómo hacer algo, usa la herramienta `ayuda` y da los pasos numerados. Esa
   herramienta devuelve VARIOS temas candidatos con una puntuación de parecido: **tú decides** si
   alguno responde de verdad a lo que preguntan. Si ninguno responde, di claramente que no tienes
   ese tema (no adaptes unos pasos que hablan de otra cosa).

Cuando uses una herramienta, apóyate en su resultado y di de dónde sale el dato
(«según tus movimientos de septiembre», «según el Resumen»).

Cuando te pidan un informe, una comparación o un desglose, ármalo así:
1. Un titular con la cifra principal («En septiembre gastaste $1.240.000»).
2. Las cifras que la expliquen, ordenadas de mayor a menor, con su nombre.
3. Si hay un periodo anterior, qué cambió y cuánto (en pesos y en porcentaje).
4. De dónde sale cada cifra: cada herramienta devuelve un campo `pantalla` con la pantalla real
   de la app; cita ESA. Si no lo trae, no te inventes el nombre de una pantalla.
Si te falta algún dato para el informe, dilo; no lo rellenes con estimaciones.
"""

def _esquema(nombre: str, descripcion: str, propiedades: dict, requeridos: list[str] | None = None):
    return {
        "type": "function",
        "function": {
            "name": nombre,
            "description": descripcion,
            "parameters": {
                "type": "object",
                "properties": propiedades,
                "required": requeridos or [],
                "additionalProperties": False,
            },
        },
    }


HERRAMIENTAS = [
    _esquema(
        "resumen",
        "Las cifras del mes: ingresos, gastos, balance, IVA y compras, más el gasto por "
        "categoría del mes y el saldo actual. Es lo que muestra la pantalla Resumen.",
        {
            "mes": {"type": "string", "description": "Mes en formato AAAA-MM (por defecto, el actual)"},
        },
    ),
    _esquema(
        "movimientos",
        "Lista movimientos (ingresos y gastos) con su fecha, monto, descripción, categoría y "
        "cuenta. Sirve para preguntas del tipo «¿cuánto gasté en mercado?».",
        {
            "desde": {"type": "string", "description": "Fecha inicial AAAA-MM-DD"},
            "hasta": {"type": "string", "description": "Fecha final AAAA-MM-DD"},
            "texto": {"type": "string", "description": "Texto a buscar en la descripción"},
            "limite": {"type": "integer", "description": f"Máximo de filas (tope {MAX_FILAS})"},
        },
    ),
    _esquema(
        "gastos_por_categoria",
        "Cuánto se gastó en cada categoría en un mes, con la variación frente al mes anterior.",
        {"mes": {"type": "string", "description": "Mes en formato AAAA-MM"}},
    ),
    _esquema(
        "evolucion",
        "Ingresos, gastos y balance de los últimos meses.",
        {"meses": {"type": "integer", "description": "Cuántos meses hacia atrás (1 a 12)"}},
    ),
    _esquema(
        "comparar",
        "Compara dos meses: ingresos, gastos, balance y el gasto por categoría de cada uno, con "
        "la diferencia. Es la herramienta de «compárame septiembre con agosto».",
        {
            "mes_a": {"type": "string", "description": "Mes principal, AAAA-MM"},
            "mes_b": {"type": "string", "description": "Mes con el que comparar, AAAA-MM"},
            "limite": {"type": "integer", "description": "Cuántas categorías devolver (tope 20)"},
        },
        ["mes_a", "mes_b"],
    ),
    _esquema(
        "detalle_de_categoria",
        "El desglose de una categoría en un mes: sus etiquetas y subetiquetas con totales, y los "
        "movimientos que la componen. Para «¿en qué se me fue la plata en Mercado?».",
        {
            "categoria": {"type": "string", "description": "Nombre de la categoría (o parte)"},
            "mes": {"type": "string", "description": "Mes AAAA-MM (por defecto, el actual)"},
        },
        ["categoria"],
    ),
    _esquema(
        "productos",
        "Lo que se compró por artículo en un mes: cuánto, cuántas veces y a qué precio promedio. "
        "Sale del detalle de las facturas.",
        {"mes": {"type": "string", "description": "Mes AAAA-MM (por defecto, el actual)"}},
    ),
    {
        "type": "function",
        "function": {
            "name": "proponer",
            "description": (
                "Propone una acción para que el USUARIO la confirme. No la ejecuta: queda "
                "pendiente y se ejecuta solo cuando el usuario pulsa confirmar en la pantalla. "
                "Úsala cuando pidan registrar un gasto o un ingreso, o etiquetar un movimiento "
                "que ya existe. Antes de proponer, asegúrate de tener el monto y la fecha (si no, "
                "pregúntalos). Después de proponer, di claramente qué se va a hacer y que falta su "
                "confirmación: NUNCA digas que ya está hecho."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["registrar_movimiento", "etiquetar_movimiento"],
                        "description": "Qué se va a hacer",
                    },
                    "datos": {
                        "type": "object",
                        "description": (
                            "Para registrar_movimiento: tipo_movimiento (gasto o ingreso), monto, "
                            "fecha (AAAA-MM-DD), descripcion, categoria y etiqueta por su nombre. "
                            "Para etiquetar_movimiento: transaccion_id (búscalo antes con "
                            "`movimientos`), categoria y etiqueta por su nombre."
                        ),
                        "properties": {
                            "tipo_movimiento": {"type": "string", "enum": ["gasto", "ingreso"]},
                            "monto": {"type": "number"},
                            "fecha": {"type": "string"},
                            "descripcion": {"type": "string"},
                            "categoria": {"type": "string"},
                            "etiqueta": {"type": "string"},
                            "transaccion_id": {"type": "string"},
                        },
                    },
                },
                "required": ["tipo", "datos"],
            },
        },
    },
    _esquema("cuentas", "Las cuentas con su saldo actual y el total.", {}),
    _esquema("tarjetas", "Las tarjetas, su tipo, su cupo y la deuda por movimientos.", {}),
    _esquema("presupuestos", "Los presupuestos activos con su monto.", {}),
    _esquema(
        "facturas",
        "Las últimas facturas subidas, con su monto, si ya se registraron y si se leyeron con IA.",
        {"limite": {"type": "integer", "description": "Máximo de filas (tope 25)"}},
    ),
    _esquema("mi_plan", "El plan del usuario: lecturas con IA, consultas, archivos y su coste.", {}),
    _esquema(
        "ayuda",
        "Los pasos para hacer algo en la app. Úsala para preguntas de «cómo hago…». Busca por "
        "significado, así que no hace falta acertar las palabras: si devuelve la lista de temas "
        "sin resultados, es que no tienes ese tema y hay que decirlo.",
        {
            "tema": {
                "type": "string",
                "description": "Tema a buscar (por ejemplo: registrar un gasto, subir una factura)",
            }
        },
    ),
]


# ── Las herramientas: todas leen con el usuario que pregunta ──────────────────────────


def _mes_por_defecto() -> str:
    return hoy().strftime("%Y-%m")


def _resumen(db: Session, usuario: Usuario, mes: str | None = None) -> dict:
    datos = reporte_panel(db, usuario.id, meses=2, mes=mes)
    return {
        "pantalla": "Resumen",
        "mes": mes or _mes_por_defecto(),
        "cifras": datos.get("kpis", {}),
        "categorias": datos.get("categorias", [])[:8],
        "saldo_actual": (saldo_cuentas(db, usuario.id) or {}).get("saldo_total"),
    }


def _movimientos(
    db: Session,
    usuario: Usuario,
    desde: str | None = None,
    hasta: str | None = None,
    texto: str | None = None,
    limite: int | None = None,
) -> list[dict]:
    consulta = select(Transaccion).where(Transaccion.usuario_id == usuario.id)
    if desde:
        consulta = consulta.where(Transaccion.fecha >= desde)
    if hasta:
        consulta = consulta.where(Transaccion.fecha <= hasta)
    if texto:
        consulta = consulta.where(Transaccion.descripcion.ilike(f"%{texto}%"))
    filas = db.scalars(
        consulta.order_by(Transaccion.fecha.desc()).limit(min(limite or 15, MAX_FILAS))
    ).all()
    return [
        {
            "fecha": str(t.fecha),
            "tipo": str(getattr(t.tipo, "value", t.tipo)),
            "monto": float(t.monto),
            "descripcion": t.descripcion or "",
        }
        for t in filas
    ]


def _gastos_por_categoria(db: Session, usuario: Usuario, mes: str) -> dict[str, float]:
    """El gasto de cada categoría en un mes, sumando sus etiquetas."""
    totales: dict[str, float] = {}
    for fila in reporte_categorias(db, usuario.id, mes):
        if fila["tipo"] != "gasto":
            continue
        totales[fila["categoria"]] = totales.get(fila["categoria"], 0.0) + fila["total"]
    return totales


def _comparar(
    db: Session, usuario: Usuario, mes_a: str, mes_b: str, limite: int | None = None
) -> dict:
    """Dos meses frente a frente: totales y por categoría, con la diferencia."""
    serie = {fila["mes"]: fila for fila in reporte_mensual(db, usuario.id, 24)}
    cat_a = _gastos_por_categoria(db, usuario, mes_a)
    cat_b = _gastos_por_categoria(db, usuario, mes_b)

    nombres = set(cat_a) | set(cat_b)
    categorias = []
    for nombre in nombres:
        antes, ahora = cat_b.get(nombre, 0.0), cat_a.get(nombre, 0.0)
        diferencia = round(ahora - antes, 2)
        categorias.append(
            {
                "categoria": nombre,
                "mes_a": round(ahora, 2),
                "mes_b": round(antes, 2),
                "diferencia": diferencia,
                "variacion_pct": round(100 * diferencia / antes, 1) if antes else None,
            }
        )
    categorias.sort(key=lambda x: -abs(x["diferencia"]))
    tope = min(limite or 12, 20)

    def _totales(mes: str) -> dict:
        fila = serie.get(mes) or {}
        ingresos = float(fila.get("ingresos") or 0)
        gastos = float(fila.get("gastos") or 0)
        return {"ingresos": ingresos, "gastos": gastos, "balance": round(ingresos - gastos, 2)}

    totales_a, totales_b = _totales(mes_a), _totales(mes_b)
    return {
        "pantalla": "Reportes",
        "mes_a": mes_a,
        "mes_b": mes_b,
        "totales": {
            "mes_a": totales_a,
            "mes_b": totales_b,
            "diferencia_gastos": round(totales_a["gastos"] - totales_b["gastos"], 2),
        },
        "categorias": categorias[:tope],
        "nota": (
            "La diferencia es mes_a menos mes_b: positiva quiere decir que en mes_a se gastó más."
        ),
    }


def _detalle_de_categoria(
    db: Session, usuario: Usuario, categoria: str, mes: str | None = None
) -> dict:
    """Una categoría abierta: sus etiquetas y los movimientos que la componen."""
    mes = mes or _mes_por_defecto()
    buscado = (categoria or "").strip().lower()
    filas = [
        fila
        for fila in reporte_categorias(db, usuario.id, mes)
        if buscado in (fila["categoria"] or "").lower()
    ]
    if not filas:
        disponibles = sorted({f["categoria"] for f in reporte_categorias(db, usuario.id, mes)})
        return {
            "mes": mes,
            "categoria": categoria,
            "nota": "No hay gastos de esa categoría en ese mes.",
            "categorias_disponibles": disponibles[:20],
        }

    etiquetas: dict[str, float] = {}
    for fila in filas:
        if fila["tipo"] == "gasto":
            nombre = fila["etiqueta"] or "Sin etiqueta"
            etiquetas[nombre] = etiquetas.get(nombre, 0.0) + fila["total"]

    gastos = db.scalars(
        select(Transaccion)
        .join(Categoria, Categoria.id == Transaccion.categoria_id)
        .where(
            Transaccion.usuario_id == usuario.id,
            func.to_char(Transaccion.fecha, "YYYY-MM") == mes,
            Transaccion.tipo == TipoTransaccion.GASTO,
            Categoria.nombre.ilike(f"%{categoria}%"),
        )
        .order_by(Transaccion.monto.desc())
        .limit(10)
    ).all()

    return {
        "pantalla": "Reportes",
        "mes": mes,
        "categoria": categoria,
        "total": round(sum(etiquetas.values()), 2),
        "etiquetas": [
            {"etiqueta": n, "total": round(v, 2)}
            for n, v in sorted(etiquetas.items(), key=lambda x: -x[1])
        ],
        "movimientos_mas_altos": [
            {"fecha": str(g.fecha), "monto": float(g.monto), "descripcion": g.descripcion or ""}
            for g in gastos
        ],
    }


def _productos(db: Session, usuario: Usuario, mes: str | None = None) -> dict:
    """Los artículos que más pesan en las compras del mes (del detalle de las facturas)."""
    mes = mes or _mes_por_defecto()
    datos = reporte_panel(db, usuario.id, meses=2, mes=mes)
    mercado = datos.get("mercado") or {}
    return {
        "pantalla": "Mercado",
        "mes": mes,
        "productos": (mercado.get("productos") or [])[:15],
        "por_etiqueta": (mercado.get("etiquetas") or [])[:15],
    }


def _proponer(db: Session, usuario: Usuario, argumentos: dict) -> dict:
    """Deja una propuesta pendiente (no ejecuta nada) y la describe."""
    datos = dict(argumentos.get("datos") or {})
    # El modelo a veces manda el tipo de movimiento dentro de `datos`: se acepta
    if datos.pop("tipo_movimiento", None):
        datos["tipo"] = argumentos.get("datos", {}).get("tipo_movimiento")
    propuesta = propuestas.proponer(db, usuario, argumentos.get("tipo") or "", datos)
    return {
        "pantalla": "Asistente (aquí mismo, para confirmar)",
        "propuesta_id": str(propuesta.id),
        "que_se_va_a_hacer": propuesta.resumen,
        "estado": "pendiente",
        "aviso": (
            "NO se ha ejecutado nada: el usuario tiene que confirmarlo. Díselo así y no des a "
            "entender que ya está hecho."
        ),
    }


def _cuentas(db: Session, usuario: Usuario) -> dict:
    datos = saldo_cuentas(db, usuario.id) or {}
    return {
        "pantalla": "Cuentas",
        "total": datos.get("saldo_total"),
        "cuentas": [
            {"nombre": c.get("nombre"), "saldo": c.get("saldo_actual")}
            for c in datos.get("cuentas", [])
        ],
    }


def _tarjetas(db: Session, usuario: Usuario) -> list[dict]:
    salida = []
    for tarjeta in db.scalars(select(Tarjeta).where(Tarjeta.usuario_id == usuario.id)).all():
        deuda = db.scalar(
            select(func.coalesce(func.sum(Transaccion.monto), 0)).where(
                Transaccion.tarjeta_id == tarjeta.id, Transaccion.tipo == "gasto"
            )
        )
        salida.append(
            {
                "nombre": tarjeta.nombre,
                "tipo": str(getattr(tarjeta.tipo, "value", tarjeta.tipo)),
                "deuda_por_movimientos": float(deuda or 0),
            }
        )
    return salida


def _presupuestos(db: Session, usuario: Usuario) -> list[dict]:
    filas = db.scalars(select(Presupuesto).where(Presupuesto.usuario_id == usuario.id)).all()
    return [
        {
            "monto": float(getattr(p, "monto", 0) or 0),
            "periodo": str(getattr(p, "periodo", "") or ""),
        }
        for p in filas[:MAX_FILAS]
    ]


def _facturas(db: Session, usuario: Usuario, limite: int | None = None) -> list[dict]:
    filas = db.scalars(
        select(Factura)
        .where(Factura.usuario_id == usuario.id)
        .order_by(Factura.creada_en.desc())
        .limit(min(limite or 10, MAX_FILAS))
    ).all()
    return [
        {
            "archivo": f.nombre_archivo,
            "fecha": str(f.fecha_detectada or f.creada_en.date()),
            "monto": float(f.monto_detectado) if f.monto_detectado is not None else None,
            "registrada": f.transaccion_id is not None,
            "leida_con_ia": bool(f.leida_con_ia),
        }
        for f in filas
    ]


def _mi_plan(db: Session, usuario: Usuario) -> dict:
    from .archivos import resumen as resumen_archivos

    cupo = cuotas.resumen(db, usuario)
    return {
        "pantalla": "Facturas (arriba, el cupo del mes)",
        "plan": cupo["plan_nombre"],
        "precio_mes": cupo["precio_mes"],
        "lecturas_ia_restantes": cupo["lecturas"]["restantes"],
        "consultas_restantes": cupo["consultas"]["restantes"],
        "gasto_ia_del_mes_usd": cupo["costo_usd"],
        "archivos": resumen_archivos(db, usuario),
    }


def _ayuda(tema: str | None = None) -> dict:
    """Los pasos de un tema, buscando por significado (embeddings locales)."""
    return manual.buscar(tema)


def ejecutar(db: Session, usuario: Usuario, nombre: str, argumentos: dict) -> object:
    """Ejecuta una herramienta. Todo lee **solo** datos de este usuario."""
    if nombre == "resumen":
        return _resumen(db, usuario, argumentos.get("mes"))
    if nombre == "movimientos":
        return {"pantalla": "Transacciones", "movimientos": _movimientos(db, usuario, **argumentos)}
    if nombre == "gastos_por_categoria":
        return {
            "pantalla": "Reportes",
            "desglose": reporte_categorias(
                db, usuario.id, argumentos.get("mes") or _mes_por_defecto()
            ),
        }
    if nombre == "evolucion":
        meses = max(1, min(int(argumentos.get("meses") or 6), 12))
        return {"pantalla": "Reportes", "meses": reporte_mensual(db, usuario.id, meses)}
    if nombre == "comparar":
        return _comparar(
            db, usuario, argumentos.get("mes_a") or "", argumentos.get("mes_b") or "",
            argumentos.get("limite"),
        )
    if nombre == "detalle_de_categoria":
        return _detalle_de_categoria(
            db, usuario, argumentos.get("categoria") or "", argumentos.get("mes")
        )
    if nombre == "productos":
        return _productos(db, usuario, argumentos.get("mes"))
    if nombre == "proponer":
        return _proponer(db, usuario, argumentos)
    if nombre == "cuentas":
        return _cuentas(db, usuario)
    if nombre == "tarjetas":
        return {"pantalla": "Tarjetas", "tarjetas": _tarjetas(db, usuario)}
    if nombre == "presupuestos":
        return {"pantalla": "Presupuestos", "presupuestos": _presupuestos(db, usuario)}
    if nombre == "facturas":
        return {"pantalla": "Facturas", "facturas": _facturas(db, usuario, argumentos.get("limite"))}
    if nombre == "mi_plan":
        return _mi_plan(db, usuario)
    if nombre == "ayuda":
        return _ayuda(argumentos.get("tema"))
    return {"error": f"La herramienta {nombre} no existe"}


def preguntar(db: Session, usuario: Usuario, pregunta: str) -> dict:
    """Responde una pregunta: comprueba cupo, deja que el modelo pida datos y cobra al final.

    El cupo se comprueba **antes** (si no hay, no se gasta un token) y la consulta se cobra solo
    si sale bien.
    """
    resumen_cupo = cuotas.resumen(db, usuario)
    if resumen_cupo["consultas"]["restantes"] < 1:
        raise cuotas.agotado(cuotas.CONSULTA_ASISTENTE, resumen_cupo)

    mensajes: list[dict] = [
        {"role": "system", "content": SISTEMA},
        {"role": "user", "content": pregunta},
    ]
    usadas: list[str] = []
    propuestas_creadas: list[dict] = []
    entrada = salida = 0
    costo = Decimal("0")

    for _ in range(MAX_VUELTAS):
        respuesta = ia.chat(mensajes, HERRAMIENTAS)
        entrada += respuesta.tokens_entrada
        salida += respuesta.tokens_salida
        costo += respuesta.costo_usd

        if not respuesta.llamadas:
            texto = respuesta.texto or (
                "No pude responder con los datos que tengo. ¿Puedes darme más detalle?"
            )
            break

        mensajes.append(
            {
                "role": "assistant",
                "content": respuesta.texto or None,
                "tool_calls": [
                    {
                        "id": llamada.id or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": llamada.nombre,
                            "arguments": json.dumps(llamada.argumentos, ensure_ascii=False),
                        },
                    }
                    for i, llamada in enumerate(respuesta.llamadas)
                ],
            }
        )
        for indice, llamada in enumerate(respuesta.llamadas):
            usadas.append(llamada.nombre)
            try:
                resultado = ejecutar(db, usuario, llamada.nombre, llamada.argumentos)
                if llamada.nombre == "proponer" and isinstance(resultado, dict):
                    propuestas_creadas.append(resultado)
            except HTTPException as error:
                # Un dato que no cuadra (categoría que no existe, monto raro) se le dice al modelo
                # para que lo corrija o lo pregunte, en vez de tumbar la respuesta
                resultado = {"error": str(error.detail)}
            except Exception as error:  # noqa: BLE001 — una herramienta rota no tumba la respuesta
                resultado = {"error": f"No pude consultar eso ({type(error).__name__})"}
            mensajes.append(
                {
                    "role": "tool",
                    "tool_call_id": llamada.id or f"call_{indice}",
                    "content": json.dumps(resultado, ensure_ascii=False, default=str)[:6000],
                }
            )
    else:
        texto = (
            "Necesitaba consultar demasiadas cosas para esta pregunta. ¿La puedes hacer más "
            "concreta?"
        )

    cuotas.consumir(db, usuario, cuotas.CONSULTA_ASISTENTE)
    cuotas.registrar_gasto(db, usuario, entrada, salida, costo)
    db.add(
        ConsultaAsistente(
            usuario_id=usuario.id,
            pregunta=pregunta[:2000],
            herramientas=", ".join(usadas) or None,
            tokens_entrada=entrada,
            tokens_salida=salida,
            costo_usd=costo,
        )
    )
    db.commit()

    return {
        "respuesta": texto,
        "propuestas": propuestas_creadas,
        "herramientas_usadas": sorted(set(usadas)),
        "tokens_entrada": entrada,
        "tokens_salida": salida,
        "costo_usd": float(costo),
    }
