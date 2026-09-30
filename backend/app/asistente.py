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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import cuotas, ia
from .models import (
    ConsultaAsistente,
    Factura,
    Presupuesto,
    Tarjeta,
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
3. Solo consultas: no puedes registrar, borrar ni cambiar nada. Si te lo piden, explica en qué
   pantalla se hace.
4. Responde corto y claro, en el idioma del usuario, con los montos en pesos colombianos.
5. Si te preguntan cómo hacer algo, usa la herramienta `ayuda` y da los pasos numerados.

Cuando uses una herramienta, apóyate en su resultado y di de dónde sale el dato
(«según tus movimientos de septiembre», «según el Resumen»).
"""

MANUAL = {
    "registrar un gasto": [
        "Entra en Movimientos y pulsa «Nuevo movimiento».",
        "Elige el tipo (gasto), el monto, la fecha y la descripción.",
        "Asígnale categoría y etiqueta: la categoría es el lugar (Casa, Apartamento) y la "
        "etiqueta el servicio o el tipo de gasto.",
        "Guarda: el saldo y los reportes se actualizan solos.",
    ],
    "subir una factura o un recibo": [
        "Entra en Facturas y elige el archivo (PDF o foto): se lee al instante.",
        "Si trae artículos, pulsa «Leer líneas» para partirla en productos.",
        "Revisa el panel «Revisa antes de registrar»: monto, fecha y artículos.",
        "Registra la compra (un solo gasto con el detalle) o confirma las líneas.",
    ],
    "leer una factura con IA": [
        "Sube la factura normalmente: el lector de Konta la lee gratis.",
        "Si la lectura queda dudosa, en esa misma factura aparece «Leer con IA» en ámbar.",
        "Púlsalo: cuesta una lectura de tu plan y reemplaza la lectura de esa factura.",
        "Si te quedas sin lecturas, puedes comprar o subir de plan.",
    ],
    "separar los gastos de casa y apartamento": [
        "Usa dos categorías: «Casa» y «Apartamento».",
        "Dentro de cada una, pon etiquetas por servicio: Acueducto, Energía, Gas, Internet.",
        "Al registrar el gasto, elige la categoría del lugar y la etiqueta del servicio.",
        "En Reportes puedes ver el total por categoría y comparar los dos lugares.",
    ],
    "saber por qué mi saldo cambió": [
        "Entra en Cuentas y mira el saldo de cada una.",
        "Abre Movimientos y filtra por esa cuenta y el mes.",
        "Ojo: el saldo solo cuenta lo que ya pasó (una transacción con fecha futura no entra "
        "hasta ese día).",
        "Si el saldo inicial no es el de tu banco, corrígelo en la cuenta.",
    ],
    "hacer un presupuesto": [
        "Entra en Presupuestos y crea uno por categoría o etiqueta.",
        "Pon el monto del mes y el periodo.",
        "La app te avisa cuando te acercas o te pasas.",
    ],
    "entender el gasto fijo del mes": [
        "Konta suma tus suscripciones y pólizas activas y reparte las anuales por mes.",
        "Lo ves en el Resumen, en la tarjeta «Gasto fijo / mes».",
        "Los cobros que están por venir aparecen en «Próximos pagos».",
    ],
    "mirar mis tarjetas y lo que debo": [
        "Entra en Tarjetas.",
        "Cada tarjeta muestra su cupo y su deuda por movimientos.",
        "Las compras con tarjeta de crédito no bajan tu saldo hasta que pagas la tarjeta.",
    ],
    "exportar o respaldar mis datos": [
        "Entra en Ajustes y busca «Respaldo».",
        "Puedes descargar tus datos para tenerlos o pasarlos a otro lado.",
    ],
    "cambiar de plan o comprar lecturas": [
        "En Facturas, arriba, tienes el cupo del mes y el botón «Ver planes».",
        "Ahí ves qué incluye cada plan y cuál tienes.",
        "El cobro en línea está en camino: por ahora se cambia escribiendo a soporte.",
    ],
}


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
        "Los pasos para hacer algo en la app. Úsala para preguntas de «cómo hago…».",
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


def _cuentas(db: Session, usuario: Usuario) -> dict:
    datos = saldo_cuentas(db, usuario.id) or {}
    return {
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
        "plan": cupo["plan_nombre"],
        "precio_mes": cupo["precio_mes"],
        "lecturas_ia_restantes": cupo["lecturas"]["restantes"],
        "consultas_restantes": cupo["consultas"]["restantes"],
        "gasto_ia_del_mes_usd": cupo["costo_usd"],
        "archivos": resumen_archivos(db, usuario),
    }


def _ayuda(tema: str | None = None) -> dict:
    if not tema:
        return {"temas": list(MANUAL)}
    buscado = tema.lower().strip()
    for clave, pasos in MANUAL.items():
        if buscado in clave or clave in buscado or any(p in clave for p in buscado.split()):
            return {"tema": clave, "pasos": pasos}
    return {
        "temas": list(MANUAL),
        "nota": "No tengo ese tema en el manual; dile al usuario que no lo tienes.",
    }


def ejecutar(db: Session, usuario: Usuario, nombre: str, argumentos: dict) -> object:
    """Ejecuta una herramienta. Todo lee **solo** datos de este usuario."""
    if nombre == "resumen":
        return _resumen(db, usuario, argumentos.get("mes"))
    if nombre == "movimientos":
        return _movimientos(db, usuario, **argumentos)
    if nombre == "gastos_por_categoria":
        return reporte_categorias(db, usuario.id, argumentos.get("mes") or _mes_por_defecto())
    if nombre == "evolucion":
        meses = max(1, min(int(argumentos.get("meses") or 6), 12))
        return reporte_mensual(db, usuario.id, meses)
    if nombre == "cuentas":
        return _cuentas(db, usuario)
    if nombre == "tarjetas":
        return _tarjetas(db, usuario)
    if nombre == "presupuestos":
        return _presupuestos(db, usuario)
    if nombre == "facturas":
        return _facturas(db, usuario, argumentos.get("limite"))
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
        "herramientas_usadas": sorted(set(usadas)),
        "tokens_entrada": entrada,
        "tokens_salida": salida,
        "costo_usd": float(costo),
    }
