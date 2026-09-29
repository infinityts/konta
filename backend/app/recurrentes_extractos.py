"""Detectar recurrentes y suscripciones en los extractos (Fase 3).

Señales, de la más fuerte a la más débil:

1. **Repetición entre cortes**: el mismo comercio en dos extractos distintos, con ~1 mes
   de diferencia (25–35 días) y montos parecidos (±20 %). Es lo que hace una suscripción.
2. **Repetición contra el historial**: el comercio ya está en las transacciones de otros
   meses (llevabas tiempo pagándolo) aunque solo tengas un extracto leído.
3. **Diccionario de servicios**: NETFLIX, SPOTIFY, PRIME VIDEO, iCloud, ChatGPT… Un
   servicio **nuevo** aparece una sola vez en su primer extracto, así que sin esta señal
   no se detectaría nunca. Por eso estos salen con confianza media y no alta.
4. **La regla de las cuotas**: una compra con `cuotas_total > 1` **nunca** es una
   suscripción. En un extracto real, RAPPI aparece 7 veces y no es una suscripción: es una
   compra a 24 cuotas. Sin esta regla, la repetición lo marcaría.
5. **Nunca** un pago, un interés, una comisión, un impuesto ni un ajuste: no son gastos
   recurrentes de consumo.

Y un detalle real: **dos cargos del mismo servicio el mismo día** (PRIME VIDEO 17.999 y
4.999) son **dos planes**, no una suscripción de 22.998. Los montos que se diferencian en
más de un 20 % se separan en candidatos distintos.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .clasificador import normalizar
from .models import (
    Extracto,
    ExtractoMovimiento,
    Periodicidad,
    Suscripcion,
    Transaccion,
)
from .recurrencia import siguiente_pago

CERO = Decimal("0")

# Servicios que se cobran solos: la señal que salva al que aparece por primera vez
DICCIONARIO: tuple[tuple[tuple[str, ...], str], ...] = (
    (("NETFLIX",), "Netflix"),
    (("SPOTIFY",), "Spotify"),
    (("PRIME VIDEO", "AMAZON PRIME", "AMZN PRIME"), "Prime Video"),
    (("DISNEY",), "Disney+"),
    (("HBO", "MAX.COM", "WARNER"), "HBO Max"),
    (("YOUTUBE",), "YouTube Premium"),
    (("ICLOUD", "APPLE.COM", "APPLE MUSIC", "ITUNES"), "Apple"),
    (("GOOGLE",), "Google"),
    (("MICROSOFT", "OFFICE 365", "XBOX"), "Microsoft 365"),
    (("AUDIBLE",), "Audible"),
    (("DEEZER",), "Deezer"),
    (("CRUNCHYROLL",), "Crunchyroll"),
    (("PARAMOUNT",), "Paramount+"),
    (("STAR+", "STAR PLUS"), "Star+"),
    (("VIX",), "ViX"),
    (("DROPBOX",), "Dropbox"),
    (("ADOBE",), "Adobe"),
    (("NOTION",), "Notion"),
    (("CHATGPT", "OPENAI"), "ChatGPT"),
    (("CANVA",), "Canva"),
    (("DUOLINGO",), "Duolingo"),
    (("LINKEDIN",), "LinkedIn"),
    (("TINDER",), "Tinder"),
    (("PLAYSTATION", "PSN"), "PlayStation Plus"),
    (("NINTENDO",), "Nintendo"),
    (("CARDIF",), "Seguro Cardif"),
    (("WAZE",), "Waze"),
)

ALTA, MEDIA, BAJA = "alta", "media", "baja"


@dataclass
class Candidato:
    """Un posible recurrente, con la evidencia de por qué se propone."""

    clave: str  # identifica el candidato para poder crearlo después
    nombre: str
    descripcion: str
    monto: Decimal
    moneda: str
    periodicidad: str
    ultima_fecha: date | None
    proximo_pago: date | None
    apariciones: int
    fechas: list[str] = field(default_factory=list)
    montos: list[str] = field(default_factory=list)
    confianza: str = BAJA
    senales: list[str] = field(default_factory=list)
    ya_es_suscripcion: bool = False
    categoria_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    en_este_extracto: bool = False


def _comercio(descripcion: str) -> str:
    """Nombre del comercio para mostrar: sin códigos de pasarela ni de terminal."""
    base = descripcion or ""
    for separador in ("*", " - ", "  "):
        if separador in base:
            partes = [p.strip() for p in base.split(separador) if p.strip()]
            # `DLO*NETFLIX.COM` -> NETFLIX.COM ; `PPRO*MICROSOFT` -> MICROSOFT
            if len(partes) > 1:
                base = max(partes, key=len)
    return base.strip()[:80]


def _conocido(descripcion: str) -> str | None:
    """¿Es un servicio de suscripción conocido? Devuelve su nombre bonito."""
    plano = normalizar(descripcion).replace(" ", "")
    for pistas, nombre in DICCIONARIO:
        for pista in pistas:
            if pista.replace(" ", "") in plano:
                return nombre
    return None


def _periodicidad_por_dias(dias: float) -> Periodicidad:
    for limite, periodicidad in (
        (10, Periodicidad.SEMANAL),
        (45, Periodicidad.MENSUAL),
        (135, Periodicidad.TRIMESTRAL),
        (300, Periodicidad.SEMESTRAL),
    ):
        if dias <= limite:
            return periodicidad
    return Periodicidad.ANUAL


def _parecidos(a: Decimal, b: Decimal) -> bool:
    """¿Son el mismo cargo? ±20 %: los servicios ajustan precios por inflación."""
    if a == CERO and b == CERO:
        return True
    mayor = max(abs(a), abs(b))
    return abs(a - b) <= mayor * Decimal("0.20")


def _agrupar_por_monto(filas: list[ExtractoMovimiento]) -> list[list[ExtractoMovimiento]]:
    """Separa montos distintos en candidatos distintos (dos planes, no uno doble)."""
    grupos: list[list[ExtractoMovimiento]] = []
    for fila in sorted(filas, key=lambda m: abs(m.valor)):
        for grupo in grupos:
            if _parecidos(grupo[0].valor, fila.valor):
                grupo.append(fila)
                break
        else:
            grupos.append([fila])
    return grupos


def _movimientos_candidatos(db: Session, usuario_id: uuid.UUID) -> list[ExtractoMovimiento]:
    """Movimientos que **pueden** ser un recurrente.

    La regla de las cuotas deja fuera las compras diferidas (así no se propone RAPPI,
    que aparece 7 veces a 24 cuotas) con **una excepción**: si el comercio es un servicio
    de suscripción conocido. Hay bancos que difieren una suscripción a cuotas —Amex
    difiere AUDIBLE a 36 cuotas de 0,29 USD—, y ahí lo que se paga al mes es la cuota.
    """
    filas = db.scalars(
        select(ExtractoMovimiento)
        .join(Extracto, Extracto.id == ExtractoMovimiento.extracto_id)
        .where(ExtractoMovimiento.usuario_id == usuario_id)
        .order_by(ExtractoMovimiento.fecha)
    ).all()
    return [
        m
        for m in filas
        if m.tipo == "compra"
        and m.valor > CERO
        and (m.descripcion or "").strip()
        and (
            not (m.cuotas_total and m.cuotas_total > 1)
            or _conocido(m.descripcion) is not None  # suscripción diferida por el banco
        )
    ]


def _fechas_del_historial(db: Session, usuario_id: uuid.UUID) -> dict[str, list[date]]:
    """Fechas por comercio de las transacciones ya registradas (otros meses)."""
    filas = db.scalars(
        select(Transaccion).where(
            Transaccion.usuario_id == usuario_id,
            Transaccion.descripcion.is_not(None),
        )
    ).all()
    por_comercio: dict[str, list[date]] = {}
    for t in filas:
        if not t.descripcion:
            continue
        por_comercio.setdefault(normalizar(t.descripcion), []).append(t.fecha)
    return por_comercio


def detectar(
    db: Session, usuario_id: uuid.UUID, extracto_id: uuid.UUID | None = None
) -> list[Candidato]:
    """Propone recurrentes a partir de los extractos leídos (y del historial).

    `extracto_id` solo sirve para marcar cuáles aparecen en ese extracto: la detección
    mira **todos** los extractos del usuario, porque la señal fuerte es la repetición
    entre cortes.
    """
    movimientos = _movimientos_candidatos(db, usuario_id)
    if not movimientos:
        return []

    del_extracto: set[uuid.UUID] = set()
    if extracto_id is not None:
        del_extracto = {
            m.id for m in movimientos if m.extracto_id == extracto_id
        }

    historial = _fechas_del_historial(db, usuario_id)
    suscripciones = db.scalars(
        select(Suscripcion).where(Suscripcion.usuario_id == usuario_id)
    ).all()
    nombres_ya = {normalizar(s.nombre).replace(" ", "") for s in suscripciones}

    por_comercio: dict[str, list[ExtractoMovimiento]] = {}
    for m in movimientos:
        por_comercio.setdefault(normalizar(m.descripcion), []).append(m)

    candidatos: list[Candidato] = []
    for clave, filas in por_comercio.items():
        for grupo in _agrupar_por_monto(filas):
            candidato = _evaluar(clave, grupo, historial, nombres_ya, bool(del_extracto & {m.id for m in grupo}))
            if candidato is not None:
                candidatos.append(candidato)

    # Alta primero, y dentro de cada confianza, el monto más alto
    orden = {ALTA: 0, MEDIA: 1, BAJA: 2}
    candidatos.sort(key=lambda c: (orden[c.confianza], -c.monto))
    return candidatos


def _evaluar(
    clave: str,
    grupo: list[ExtractoMovimiento],
    historial: dict[str, list[date]],
    nombres_ya: set[str],
    en_este_extracto: bool,
) -> Candidato | None:
    """Decide si un grupo de cargos iguales es un recurrente, y con qué evidencia."""
    fechas = sorted({m.fecha for m in grupo if m.fecha})
    ultimo = grupo[-1]
    # El monto es el del último cargo: es el que se va a repetir. Si el banco lo difirió
    # a cuotas, lo que se cobra al mes es la cuota.
    diferida = bool(ultimo.cuotas_total and ultimo.cuotas_total > 1)
    monto = abs(ultimo.cuota_mes) if diferida and ultimo.cuota_mes else abs(ultimo.valor)
    moneda = ultimo.moneda

    conocida = _conocido(ultimo.descripcion)
    fechas_historial = sorted(set(historial.get(clave, [])) - set(fechas))

    senales: list[str] = []
    confianza = BAJA
    if diferida:
        senales.append(
            f"el banco la difirió a {ultimo.cuotas_n}/{ultimo.cuotas_total} cuotas: "
            "lo que pagas al mes es la cuota"
        )

    # 1) Repetición entre cortes (o dentro del mismo si son meses distintos)
    if len(fechas) >= 2:
        dias = [(fechas[i + 1] - fechas[i]).days for i in range(len(fechas) - 1)]
        promedio = sum(dias) / len(dias)
        if 1 <= promedio <= 400:
            senales.append(
                f"aparece {len(fechas)} veces con {round(promedio)} días entre cargos"
            )
            confianza = ALTA if 20 <= promedio <= 40 else MEDIA

    # 2) Repetición contra el historial de transacciones
    if fechas_historial:
        senales.append(
            f"ya estaba en tus movimientos ({len(fechas_historial)} mes(es) más)"
        )
        confianza = ALTA if confianza == ALTA else MEDIA

    # 3) Diccionario de servicios que se cobran solos
    if conocida is not None:
        senales.append(f"«{conocida}» es un servicio de cobro periódico")
        if confianza == BAJA:
            # Un servicio nuevo aparece una sola vez en su primer extracto
            confianza = MEDIA

    if not senales:
        return None

    dias_promedio = 30.0
    if len(fechas) >= 2:
        dias_promedio = sum(
            (fechas[i + 1] - fechas[i]).days for i in range(len(fechas) - 1)
        ) / (len(fechas) - 1)
    elif fechas_historial:
        todas = sorted([*fechas_historial, *fechas])
        dias_promedio = (todas[-1] - todas[0]).days / max(1, len(todas) - 1)
    periodicidad = _periodicidad_por_dias(max(dias_promedio, 1))

    nombre_plano = (conocida or _comercio(ultimo.descripcion)).upper().replace(" ", "")
    return Candidato(
        clave=f"{clave}|{monto}",
        nombre=(conocida or _comercio(ultimo.descripcion))[:120],
        descripcion=ultimo.descripcion,
        monto=monto,
        moneda=moneda,
        periodicidad=periodicidad.value,
        ultima_fecha=ultimo.fecha,
        proximo_pago=siguiente_pago(periodicidad, ultimo.fecha) if ultimo.fecha else None,
        apariciones=len(fechas),
        fechas=[f.isoformat() for f in fechas],
        montos=[str(abs(m.valor)) for m in grupo],
        confianza=confianza,
        senales=senales,
        ya_es_suscripcion=any(nombre_plano in n or n in nombre_plano for n in nombres_ya if n),
        categoria_id=ultimo.categoria_id,
        etiqueta_id=ultimo.etiqueta_id,
        en_este_extracto=en_este_extracto,
    )
