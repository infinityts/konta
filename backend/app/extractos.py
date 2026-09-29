"""Lectura de extractos bancarios (PDF y Excel) y conciliación.

De los tres extractos reales que se usaron para calibrar salieron cuatro verdades que
mandan en el diseño de este módulo:

1. **En PDF hay que leer por coordenadas, no por líneas.** El mismo dato viene partido
   (`"Núme ro de tarje ta CMR"`), duplicado (`$9.568,71$9.568,71`) o pegado a otro sin
   separador (`$108.515,3125,87 US D`). Parseando con `(y, x)` cada valor cae en su
   columna y los pegotes desaparecen.
2. **Un movimiento puede ocupar varias líneas.** En el PDF de Davivienda la descripción
   se parte en dos y los montos vienen en la cuarta línea, así que la tabla se lee con
   una máquina de estados: se abre un movimiento cuando aparece la fecha y se cierra
   cuando aparece la columna de valor.
3. **El extracto trae sus propios totales**, y ahí está la red de seguridad: si las
   filas no cuadran con lo que el banco declara, se avisa **antes** de importar nada.
4. **Lo anterior al periodo no es un gasto nuevo.** Los extractos listan el capital de
   compras viejas; importarlas duplicaría el gasto. Se marcan como informativas.

La conciliación tiene dos niveles: por **componentes** (compras, abonos, intereses…,
con tolerancia porque el banco redondea el total) y **por fila**
(`valor_pendiente ≈ cuota × (cuotas_total − cuotas_n)`), que detecta un renglón mal
leído aunque los totales cuadren.
"""

from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

from .dinero import Formato, buscar_montos, parsear_monto, quitar_duplicado
from .lineas import sin_acentos
from .recurrencia import hoy

CERO = Decimal("0")
TOLERANCIA_TOTAL = Decimal("1")  # el banco redondea el "pago total" (0,68 en el Amex)
TOLERANCIA_FILA = Decimal("5")  # céntimos de redondeo en el invariante por fila

# --------------------------------------------------------------------------- #
# Tipos de movimiento (texto validado en Python, no ENUM de PostgreSQL)
# --------------------------------------------------------------------------- #

TIPOS_MOVIMIENTO = (
    "compra",
    "pago",  # abono a la tarjeta o ingreso a la cuenta
    "interes",
    "comision",  # cuota de manejo, comisiones, seguros
    "impuesto",  # GMF / 4x1000
    "ajuste",  # se cancela con otro renglón: no es plata que se movió
    "retiro",
    "transferencia",
    "nomina",
    "otro",
)

# Vocabulario para deducir el tipo. Se compara sin espacios ni acentos.
_PISTAS_TIPO: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("ajuste", (r"AJUSTE", r"REVERSO", r"NOTA CREDITO", r"NOTA DEBITO", r"CAMBIO CUOTAS")),
    ("interes", (r"INTERES", r"\bMORA\b")),
    ("impuesto", (r"\bGMF\b", r"4X1000", r"IMPUESTO", r"\bIVA\b")),
    ("comision", (r"CUOTA DE MANEJO", r"COMISION", r"SEGURO", r"COBRO")),
    ("nomina", (r"NOMINA", r"SALARIO")),
    # OJO: «pago» solo cuando es un pago **de tu deuda**. `PAGO TARJETA`, `PAGOS POR
    # PSE`, `ABONO`… Un comercio que se llama «MERCADO PAGO» no es un pago tuyo (ver
    # `_PROCESADORES`): clasificarlo como pago se saltaba 20.206,28 de cuotas del mes.
    (
        "pago",
        (
            r"PAGOTARJETA",
            r"PAGOSPORPSE",
            r"PAGOSUCURSAL",
            r"PAGOEFECTIVO",
            r"PAGONACIONAL",
            r"ABONO",
            r"CANCELACION",
            r"RECIBIDO",
        ),
    ),
    ("retiro", (r"RETIRO", r"CAJERO", r"AVANCE")),
    ("transferencia", (r"TRANSFERENCIA", r"TRASLADO")),
)


# Pasarelas y comercios cuyo nombre lleva «pago» dentro: son compras, no pagos
_PROCESADORES = ("MERCADOPAGO", "PAGOSEPAYCO", "PAYU", "WOMPI", "EPAYCO", "GPAY", "APPLEPAY")


def _plano(texto: str) -> str:
    """Mayúsculas, sin acentos y **sin espacios**: así casa `Núme ro` con `NUMERO`."""
    return re.sub(r"\s+", "", sin_acentos(texto or "").upper())


def _legible(texto: str) -> str:
    """Mayúsculas, sin acentos y con espacios simples (para patrones con límites)."""
    return re.sub(r"\s+", " ", sin_acentos(texto or "").upper()).strip()


def _con_espacios(texto: str) -> str:
    """Mayúsculas, sin acentos y sin puntuación, conservando los espacios.

    `Pagos / abonos` y `Pagos y abonos` tienen que casar con la misma clave.
    """
    limpio = re.sub(r"[^A-Z0-9 ]+", " ", sin_acentos(texto or "").upper())
    return re.sub(r"\s+", " ", limpio).strip()


def patron_tolerante(clave: str) -> re.Pattern[str]:
    """Patrón que tolera espacios y puntuación **dentro** de la etiqueta.

    Los PDF de banco parten las etiquetas (`"Pe riodo facturado"`) y meten signos
    (`"Pagos / abonos"`), así que buscar la palabra tal cual falla. Entre carácter y
    carácter se permite cualquier cosa que no sea letra ni número; los números del
    texto **no se tocan**, porque son el valor que se va a leer después.
    """
    letras = [c for c in _plano(clave) if c.isalnum()]
    return re.compile(r"[\W_]*".join(re.escape(c) for c in letras), re.IGNORECASE)


def tipo_de_movimiento(descripcion: str, valor: Decimal, cuotas_total: int | None) -> str:
    """Deduce qué es el renglón: compra, pago, interés, comisión, impuesto, ajuste…"""
    legible = _legible(descripcion)
    plano = _plano(descripcion)
    es_procesador = any(p in plano for p in _PROCESADORES)
    for tipo, pistas in _PISTAS_TIPO:
        if tipo == "pago" and es_procesador and valor > 0:
            continue  # «MERCADO PAGO» es el comercio, no un pago de tu deuda
        # Se busca en las dos formas: con espacios (`PAGO TARJETA`) y sin ellos. Los PDF
        # de banco parten las palabras (`PAG O TARJETA C MR`), así que la forma sin
        # espacios también tiene que casar.
        if any(re.search(p, legible) or re.search(p, plano) for p in pistas):
            return tipo
    if valor < 0:
        return "pago"  # negativo en un extracto de tarjeta es plata que entra
    return "compra" if valor > 0 else "otro"


# --------------------------------------------------------------------------- #
# Estructuras
# --------------------------------------------------------------------------- #


@dataclass
class Fragmento:
    y: float
    x: float
    texto: str


@dataclass
class MovimientoCrudo:
    fecha: date | None
    descripcion: str
    valor: Decimal
    moneda: str = "COP"
    saldo: Decimal | None = None
    monto_original: Decimal | None = None
    moneda_original: str | None = None
    tasa_cambio: Decimal | None = None
    cuotas_n: int | None = None
    cuotas_total: int | None = None
    cuota_mes: Decimal | None = None
    valor_pendiente: Decimal | None = None
    tasa_ea: Decimal | None = None
    titular: str | None = None
    es_informativo: bool = False
    tipo: str = "otro"

    def cerrar(self) -> MovimientoCrudo:
        self.tipo = tipo_de_movimiento(self.descripcion, self.valor, self.cuotas_total)
        return self


@dataclass
class ExtractoCrudo:
    tipo: str = "tarjeta"  # tarjeta | cuenta
    moneda: str = "COP"
    banco: str | None = None
    periodo_desde: date | None = None
    periodo_hasta: date | None = None
    fecha_corte: date | None = None
    fecha_pago: date | None = None
    saldo_anterior: Decimal | None = None
    compras: Decimal | None = None
    intereses: Decimal | None = None
    intereses_mora: Decimal | None = None
    otros_cargos: Decimal | None = None
    abonos: Decimal | None = None
    pago_total: Decimal | None = None
    pago_minimo: Decimal | None = None
    cupo_total: Decimal | None = None
    cupo_disponible: Decimal | None = None
    # La tasa que declara el corte (fracción), si la declara
    tasa_mv: Decimal | None = None
    tasa_ea: Decimal | None = None
    movimientos: list[MovimientoCrudo] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    # El extracto llama «consumos del mes» al capital facturado (CMR) y no al valor de
    # las compras: cambia contra qué se concilia
    compras_es_capital: bool = False

    @property
    def monedas(self) -> list[str]:
        vistas: list[str] = []
        for m in self.movimientos:
            if m.moneda not in vistas:
                vistas.append(m.moneda)
        return vistas


# --------------------------------------------------------------------------- #
# Metadata: las cifras que declara el extracto
# --------------------------------------------------------------------------- #

_ETIQUETAS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pago_total", ("TU PAGO TOTAL ES", "PAGO TOTAL")),
    ("pago_minimo", ("TU PAGO MINIMO ES", "PAGO MINIMO")),
    ("cupo_disponible", ("TIENES DISPONIBLE", "CUPO DISPONIBLE")),
    ("cupo_total", ("CUPO TOTAL DE TU TARJETA", "CUPO TOTAL DE TU TARJETA CMR", "CUPO TOTAL")),
    ("saldo_anterior", ("SALDO PERIODO ANTERIOR", "SALDO ANTERIOR")),
    ("compras", ("CONSUMOS DEL MES FACTURADOS", "CONSUMOS DEL MES", "COMPRAS DEL MES")),
    ("intereses", ("INTERESES CORRIENTES DEL MES", "INTERESES CORRIENTES")),
    ("intereses_mora", ("INTERESES DE MORA", "INTERESES MORA")),
    ("abonos", ("PAGOS INCLUYE ABONOS", "PAGOS ABONOS", "ABONO")),
    ("otros_cargos", ("OTROS CARGOS", "CUOTA DE MANEJO")),
    ("tasa_ea", ("TASA EFECTIVA ANUAL", "TASA E.A", "INTERES ANUAL")),
    ("tasa_mv", ("TASA M.V", "TASA MENSUAL", "INTERES MENSUAL")),
)

# Una etiqueta puede aparecer antes de otra muy parecida: `Capital facturado consumos del
# mes` **no** es el `Consumos del mes` del pago total.
_EVITAR: dict[str, tuple[str, ...]] = {"compras": ("CAPITAL FACTURADO", "SALDO ANTERIOR")}

_BANCOS = (
    ("Davivienda", ("DAVIVIENDA",)),
    ("Falabella", ("CMR", "FALABELLA")),
    ("Amex", ("AMERICAN EXPRESS", "AMEX")),
    ("Bancolombia", ("BANCOLOMBIA",)),
    ("Banco de Bogota", ("BANCO DE BOGOTA",)),
    ("Nu", ("NU COLOMBIA", "NUBANK")),
)


def metadatos(texto: str, extracto: ExtractoCrudo) -> None:
    """Saca del texto del extracto sus propias cifras, tolerando etiquetas partidas."""
    base = re.sub(r"[ \t]+", " ", sin_acentos(texto or "").upper())
    plano = _plano(base)
    for banco, pistas in _BANCOS:
        if extracto.banco is None and any(p in plano for p in pistas):
            extracto.banco = banco

    for campo, claves in _ETIQUETAS:
        if getattr(extracto, campo) is not None:
            continue
        for clave in claves:
            elegido = None
            for m in patron_tolerante(clave).finditer(base):
                antes = _plano(base[max(0, m.start() - 30) : m.start()])
                if any(_plano(e) in antes for e in _EVITAR.get(campo, ())):
                    continue  # es otra etiqueta parecida (p.ej. `Capital facturado consumos…`)
                elegido = m
                break
            if elegido is None:
                continue
            ventana = base[elegido.end() : elegido.end() + 120]
            if campo in ("tasa_ea", "tasa_mv"):
                tasa = _tasa_de(ventana)
                if tasa is not None:
                    setattr(extracto, campo, tasa)
                    break
                continue
            valores = buscar_montos(ventana, Formato.CO)
            if valores:
                setattr(extracto, campo, valores[0])
                if campo == "compras" and _plano(clave) == "CONSUMOSDELMESFACTURADOS":
                    extracto.compras_es_capital = True
                break

    # El periodo y las fechas de corte y pago: la ventana tiene que ser amplia, porque en
    # algunos extractos la etiqueta y sus fechas están en columnas distintas
    if extracto.periodo_desde is None:
        # `Desde … / Hasta …` es lo más explícito (Davivienda); si no está, se busca
        # alrededor de la etiqueta del periodo
        m_desde = patron_tolerante("DESDE").search(base)
        m_hasta = patron_tolerante("HASTA").search(base)
        if m_desde and m_hasta:
            d1 = _fecha_de(base[m_desde.end() : m_desde.end() + 40])
            d2 = _fecha_de(base[m_hasta.end() : m_hasta.end() + 40])
            if d1 and d2:
                extracto.periodo_desde, extracto.periodo_hasta = d1, d2
    if extracto.periodo_desde is None:
        for clave in ("PERIODO FACTURADO", "PERIODO DE FACTURACION", "FECHAS IMPORTANTES"):
            m = patron_tolerante(clave).search(base)
            if not m:
                continue
            ventana = base[m.end() : m.end() + 300]
            fechas = _fechas_con_anio_inferido(ventana)
            if len(fechas) >= 2:
                if fechas[0] > fechas[1]:
                    # Fechas al revés = la etiqueta no era la del periodo. No se inventa:
                    # un periodo falso marcaría todo el detalle como «de meses anteriores»
                    extracto.avisos.append(
                        "No se pudo leer el periodo facturado (las fechas salen al revés)"
                    )
                    break
                extracto.periodo_desde, extracto.periodo_hasta = fechas[0], fechas[1]
                break
    if extracto.fecha_pago is None:
        for clave in ("PAGAR ANTES DE", "PAGA ANTES DEL", "FECHA DE PAGO"):
            m = patron_tolerante(clave).search(base)
            if m:
                f = _fecha_de(base[m.end() : m.end() + 80])
                if f:
                    extracto.fecha_pago = f
                    break
    if extracto.fecha_corte is None:
        m = patron_tolerante("FECHA DE CORTE").search(base)
        if m:
            f = _fecha_de(base[m.end() : m.end() + 80])
            if f:
                extracto.fecha_corte = f


# --------------------------------------------------------------------------- #
# PDF: fragmentos con posición -> renglones -> columnas
# --------------------------------------------------------------------------- #


def _fragmentos_de_pagina(pagina) -> list[Fragmento]:
    frags: list[Fragmento] = []

    def visitor(texto, cm, tm, font, size):
        limpio = quitar_duplicado((texto or "").strip())
        if limpio:
            frags.append(Fragmento(y=round(tm[5], 1), x=round(tm[4], 1), texto=limpio))

    try:
        pagina.extract_text(visitor_text=visitor)
    except Exception:  # noqa: BLE001 — un PDF raro no debe tumbar la subida
        return []
    return frags


def leer_pdf(contenido: bytes, password: str | None = None) -> tuple[str, list[list[Fragmento]]]:
    """Devuelve el texto del PDF (con `layout`) y sus fragmentos con posición."""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(contenido))
    if reader.is_encrypted and not (password and reader.decrypt(password)):
        raise ValueError("El PDF está protegido y la contraseña no es correcta")

    textos: list[str] = []
    por_pagina: list[list[Fragmento]] = []
    for pagina in reader.pages:
        try:
            textos.append(pagina.extract_text(extraction_mode="layout") or "")
        except Exception:  # noqa: BLE001 — si el modo layout falla, sirve el normal
            textos.append(pagina.extract_text() or "")
        por_pagina.append(_fragmentos_de_pagina(pagina))
    return "\n".join(textos), por_pagina


def renglones(
    frags: list[Fragmento], tolerancia: float = 3.0, descendente: bool = True
) -> list[list[Fragmento]]:
    """Agrupa por `y` (mismo renglón) y ordena por `x` (izquierda a derecha).

    `descendente` dice cómo se lee la página: hay PDF donde `y` crece hacia arriba
    (Davivienda) y otros donde crece hacia abajo (CMR). Se detecta solo, pero se puede
    forzar.
    """
    clave = (lambda f: (-f.y, f.x)) if descendente else (lambda f: (f.y, f.x))
    filas: list[list[Fragmento]] = []
    for f in sorted(frags, key=clave):
        if filas and abs(filas[-1][0].y - f.y) <= tolerancia:
            filas[-1].append(f)
        else:
            filas.append([f])
    for fila in filas:
        fila.sort(key=lambda f: f.x)
    return filas


# Sinónimos de columnas (normalizados sin espacios). El orden importa: lo más
# específico primero, para que `VALOR PENDIENTE` no se confunda con `VALOR`.
_SINONIMOS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("valor_pendiente", ("VALORPENDIENTE", "SALDOPENDIENTE", "CAPITALPENDIENTE", "PENDIENTE")),
    ("cuota_mes", ("CUOTAAPAGARESTEMES", "CUOTAAPAGAR", "VALORCUOTA", "CUOTAMENSUAL")),
    ("capital_periodo", ("CAPITALFACTURADODELPERIODO", "CAPITALFACTURADO")),
    ("original", ("VRMONEDAORIG", "MONEDAORIG", "MONEDAORIGEN", "USD")),
    ("cuotas", ("NUMERODECUOTAS", "NDECUOTAS", "CUOTAS", "CUOTA")),
    ("valor", ("VALORDELMOVIMIENTO", "VALORMOVIMIENTO", "VALORTRANSACCION", "VALOR", "IMPORTE", "MONTO")),
    ("descripcion", ("DETALLEDEMOVIMIENTO", "DETALLE", "DESCRIPCION", "CONCEPTO", "TRANSACCION", "MOVIMIENTO")),
    ("titular", ("TITULAROADICIONAL", "TITULAR", "ADICIONAL")),
    ("saldo", ("SALDO",)),
    ("fecha", ("FECHA",)),
    # La tasa anual antes que la mensual: `INTERES ANUAL` también contiene `INTERES`
    ("tasa", ("TASAEFECTIVAANUAL", "TASAEA", "INTERESANUAL", "TASA")),
    # El Excel de Amex la llama `Interés mensual (%)`, en su propia columna
    ("tasa_mv", ("INTERESMENSUAL", "TASAMV", "TASAMENSUAL")),
)


def campo_de(encabezado: str) -> str | None:
    plano = _plano(encabezado)
    for campo, claves in _SINONIMOS:
        if any(k in plano for k in claves):
            return campo
    return None


def columnas_por_encabezado(
    frags: list[Fragmento],
) -> tuple[float, list[tuple[str, float]], bool] | None:
    """Deduce la `x` de cada columna desde el encabezado de la tabla.

    El encabezado de un extracto puede venir **partido en varias líneas y a distintas
    alturas** (el CMR reparte `Valor del` / `movimiento`, `Cuota a` / `pagar` /
    `este mes` en una banda de 15 puntos). Por eso no se buscan renglones contiguos
    sino la **banda de `y`** donde se acumulan palabras de encabezado, y luego se
    juntan los fragmentos de cada columna por su `x`.

    Las columnas salen de las posiciones del propio encabezado: el mismo código sirve
    para bancos distintos, solo cambian las palabras.
    """
    candidatos = [
        f
        for f in frags
        if campo_de(f.texto) or _plano(f.texto) in ("VALOR", "MOVIMIENTO", "CUOTA", "NUMERO", "DE")
    ]
    candidatos = [f for f in candidatos if len(f.texto) <= 40]
    if len(candidatos) < 4:
        return None

    # Banda de y con más palabras de encabezado (el encabezado real)
    bandas: list[list[Fragmento]] = []
    for f in sorted(candidatos, key=lambda f: -f.y):
        if bandas and abs(bandas[-1][0].y - f.y) <= 40:
            bandas[-1].append(f)
        else:
            bandas.append([f])
    banda = max(bandas, key=len)
    if len(banda) < 4:
        return None
    y_min, y_max = min(f.y for f in banda), max(f.y for f in banda)

    # Todos los fragmentos de esa banda (no solo los candidatos) agrupados por x
    en_banda = [f for f in frags if y_min - 12 <= f.y <= y_max + 12]
    clusters: list[list[Fragmento]] = []
    for f in sorted(en_banda, key=lambda f: f.x):
        if clusters and f.x - clusters[-1][-1].x <= 20:
            clusters[-1].append(f)
        else:
            clusters.append([f])

    columnas: list[tuple[str, float]] = []
    for cluster in sorted(clusters, key=lambda c: c[0].x):
        nombre = " ".join(f.texto for f in sorted(cluster, key=lambda f: (-f.y, f.x)))
        campo = campo_de(nombre)
        x = sum(f.x for f in cluster) / len(cluster)
        if campo and all(campo != c for c, _ in columnas):
            columnas.append((campo, x))
    if len(columnas) >= 3 and any(
        c in ("valor", "capital_periodo", "valor_pendiente") for c, _ in columnas
    ):
        return y_max, columnas, _hacia_abajo(frags, (y_min + y_max) / 2)
    return None


def _hacia_abajo(frags: list[Fragmento], y_banda: float) -> bool:
    """¿El contenido del extracto está en `y` mayor o menor que el encabezado?

    Los PDF no se ponen de acuerdo con el origen de coordenadas: en el CMR los datos
    tienen `y` mayor que el encabezado y en Davivienda menor. Se deduce de las fechas.
    """
    patron = re.compile(r"\d{2}[/-]\d{2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}")
    con_fecha = [f for f in frags if patron.search(f.texto)]
    abajo = len([f for f in con_fecha if f.y > y_banda])
    arriba = len([f for f in con_fecha if f.y < y_banda])
    return abajo >= arriba


def _asignar(fila: list[Fragmento], columnas: list[tuple[str, float]]) -> dict[str, str]:
    """Reparte los fragmentos del renglón entre las columnas por cercanía en `x`."""
    celdas: dict[str, list[str]] = {}
    for f in fila:
        campo, _ = min(columnas, key=lambda c: abs(c[1] - f.x))
        celdas.setdefault(campo, []).append(f.texto)
    return {campo: " ".join(textos) for campo, textos in celdas.items()}


def movimientos_desde_filas(
    frags: list[Fragmento],
    y_encabezado: float,
    columnas: list[tuple[str, float]],
    moneda: str,
    hacia_abajo: bool = True,
) -> list[MovimientoCrudo]:
    """Máquina de estados: se abre con la fecha y se cierra con el valor.

    Los renglones intermedios son la descripción (que en los PDF se parte en varias
    líneas) y una línea de `T.C.` aporta la tasa de cambio de la compra anterior.
    """
    movimientos: list[MovimientoCrudo] = []
    actual: MovimientoCrudo | None = None
    ultimo: MovimientoCrudo | None = None

    if hacia_abajo:
        datos = [f for f in frags if f.y > y_encabezado + 4]
        orden_descendente = False
    else:
        datos = [f for f in frags if f.y < y_encabezado - 4]
        orden_descendente = True
    for fila in renglones(datos, descendente=orden_descendente):
        texto_fila = " ".join(f.texto for f in fila)
        if re.search(
            r"(?i)^\s*(Gastos de cobranza|Castigos|Las tarifas|Revisor[ií]a|Cons[uú]ltala|"
            r"Informaci[oó]n de inter[eé]s|Anexo)",
            texto_fila,
        ):
            break

        celdas = _asignar(fila, columnas)
        fecha = _fecha_de(celdas.get("fecha", ""))
        valor = _valor_de(celdas.get("valor")) if celdas.get("valor") else None
        if valor is None:
            valor = _valor_de(celdas.get("capital_periodo"))

        # La tasa de cambio de una compra internacional viene en su propio renglón
        if "T.C" in _plano(texto_fila):
            destino = actual or ultimo
            if destino is not None:
                tasa = buscar_montos(texto_fila, Formato.CO)
                if tasa:
                    destino.tasa_cambio = max(tasa)
            continue

        if fecha is not None:
            if actual is not None and actual.valor != CERO:
                movimientos.append(actual.cerrar())
                ultimo = movimientos[-1]
            actual = MovimientoCrudo(fecha=fecha, descripcion="", valor=CERO, moneda=moneda)

        if actual is None:
            continue

        descripcion = (celdas.get("descripcion") or "").strip()
        if descripcion:
            actual.descripcion = f"{actual.descripcion} {descripcion}".strip()

        if valor is not None:
            actual.valor = valor
        if actual.tasa_ea is None:
            actual.tasa_ea = _tasa_de(celdas.get("tasa"))
        pendiente = _valor_de(celdas.get("valor_pendiente"))
        if pendiente is not None:
            actual.valor_pendiente = pendiente
        cuota = _valor_de(celdas.get("cuota_mes"))
        if cuota is None:
            cuota = _valor_de(celdas.get("capital_periodo"))
        if cuota is not None:
            actual.cuota_mes = cuota
        cuotas = _cuotas_de(celdas.get("cuotas", ""))
        if cuotas:
            actual.cuotas_n, actual.cuotas_total = cuotas
        titular = (celdas.get("titular") or "").strip()
        if titular and _plano(titular) in ("T", "TT", "A", "AA"):
            actual.titular = titular[:1].upper()
        # Compra internacional: el banco imprime el monto **en divisa** y solo la cuota y
        # el pendiente en pesos. Se detecta porque la celda de valor no trae `$`.
        original = celdas.get("original") or ""
        hay_divisa = "USD" in _plano(original) or bool(re.search(r"(?i)us\s*d", texto_fila))
        if hay_divisa and actual.valor > 0:
            actual.monto_original = actual.valor
            actual.moneda_original = "USD"
            actual.moneda = "USD"
            actual.valor = actual.valor  # se queda en su moneda: sumar pesos y dólares no significa nada

        if actual.valor != CERO:
            movimientos.append(actual.cerrar())
            ultimo = movimientos[-1]
            actual = None

    if actual is not None and actual.valor != CERO:
        movimientos.append(actual.cerrar())
    return movimientos


# --------------------------------------------------------------------------- #
# Helpers de campos
# --------------------------------------------------------------------------- #

_MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "set": 9, "oct": 10, "nov": 11, "dic": 12,
}


def _fechas_con_anio_inferido(texto: str) -> list[date]:
    """Fechas del texto, deduciendo el año de las que no lo traen.

    Los extractos escriben `17 ago` y `15 sep. 2026` juntos (Amex): la primera no trae
    año, así que se toma el de la segunda.
    """
    halladas: list[tuple[date | None, int | None, int, int, str]] = []
    anios: list[int] = []
    for m in re.finditer(r"(\d{1,2})\s*([A-Z]{3,})\.?,?\s*(\d{4})?", texto):
        mes = _MESES.get(_plano(m.group(2))[:3].lower())
        if not mes:
            continue
        anio = int(m.group(3)) if m.group(3) else None
        if anio:
            anios.append(anio)
        halladas.append((None, anio, int(m.group(1)), mes, m.group(0)))
    for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", texto):
        anio, mes, dia = int(m.group(1)), int(m.group(2)), int(m.group(3))
        anios.append(anio)
        halladas.append((date(anio, mes, dia), anio, dia, mes, m.group(0)))
    for m in re.finditer(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", texto):
        dia, mes, anio = int(m.group(1)), int(m.group(2)), int(m.group(3))
        anio = anio + 2000 if anio < 100 else anio
        anios.append(anio)
        halladas.append((date(anio, mes, dia), anio, dia, mes, m.group(0)))

    referencia = max(anios) if anios else hoy().year
    salida: list[date] = []
    for directa, anio, dia, mes, _ in halladas:
        try:
            d = directa or date(anio or referencia, mes, dia)
        except ValueError:
            continue
        if d not in salida:
            salida.append(d)
    return salida


def _fecha_de(texto: str) -> date | None:
    """Busca una fecha **dentro** del texto.

    En el PDF de Davivienda la columna de la tarjeta viene pegada a la fecha
    (`Virtual 2025-02-13`), así que parsear la cadena completa no sirve: hay que
    encontrarla.
    """
    from .importacion import _parse_fecha

    plano = (texto or "").strip()
    if not plano:
        return None

    for patron in (
        r"\d{4}-\d{2}-\d{2}",
        r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
    ):
        for m in re.finditer(patron, plano):
            d = _parse_fecha(m.group(0))
            if d is not None:
                return d

    m = re.search(
        r"(\d{1,2})\s*(?:de\s*)?([a-zA-Záéíóú]{3,})\.?,?\s*(?:de\s*)?(\d{4})", plano
    )
    if m:
        mes = _MESES.get(_plano(m.group(2))[:3].lower())
        if mes:
            return date(int(m.group(3)), mes, int(m.group(1)))
    m = re.search(r"([a-zA-Záéíóú]{3,})\.?\s*(\d{1,2}),?\s*(\d{4})", plano)
    if m:
        mes = _MESES.get(_plano(m.group(1))[:3].lower())
        if mes:
            return date(int(m.group(3)), mes, int(m.group(2)))
    return None


def _valor_de(texto: str | None) -> Decimal | None:
    """Valor de una celda ya aislada (por eso aquí sí se tolera suciedad)."""
    if not texto:
        return None
    unico = parsear_monto(quitar_duplicado(texto), Formato.CO)
    if unico is not None:
        return unico
    valores = buscar_montos(texto, Formato.CO)
    return valores[0] if valores else None


def _numero_tasa(bruto: str) -> Decimal | None:
    """Un número de tasa, que **no** es dinero: puede tener 4 decimales (`29.2215`)."""
    s = (bruto or "").strip()
    if not s:
        return None
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".") if s.rfind(",") > s.rfind(".") else s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _tasa_de(texto: str | None) -> Decimal | None:
    """La tasa E.A. de una celda, como fracción.

    El extracto de Davivienda trae las dos en la misma celda (`1,9648% 26,30%`): la anual
    es siempre la mayor, así que se toma esa. El Excel de Amex la trae como número de
    porcentaje con cuatro decimales (`29.2215`), así que lo que pasa de 1 se divide entre 100.
    """
    if not texto:
        return None
    candidatos = [
        v for v in (_numero_tasa(m.group(1)) for m in re.finditer(r"(\d+(?:[.,]\d+)?)", texto)) if v
    ]
    if not candidatos:
        return None
    tasa = max(candidatos)
    if tasa > 1:  # viene en porcentaje
        tasa = tasa / 100
    if not (Decimal("0.0001") <= tasa <= Decimal("1")):
        return None
    return tasa.quantize(Decimal("0.0001"))


def _cuotas_de(texto: str) -> tuple[int, int] | None:
    """`7 de 24`, y tolera que la tasa venga pegada (`1 de 128,15%` = `1 de 1` + `28,15%`)."""
    # Dos formas: `7 de 24` (PDF) y `1/1` (Excel de Amex)
    m = re.search(r"(\d{1,3})\s*(?:de|/)\s*(\d{1,4})", texto or "", re.IGNORECASE)
    if not m:
        return None
    n_txt, total_txt = m.group(1), m.group(2)
    # Si justo después viene `,dd` es la tasa pegada: sus 2 enteros no son cuotas
    resto = (texto or "")[m.end() : m.end() + 4]
    if resto.startswith(",") and len(total_txt) > 2:
        total_txt = total_txt[:-2]
    try:
        n, total = int(n_txt), int(total_txt)
    except ValueError:
        return None
    if not (1 <= n <= 120 and 1 <= total <= 120 and n <= total):
        return None
    return n, total


# --------------------------------------------------------------------------- #
# Excel
# --------------------------------------------------------------------------- #


def leer_excel(contenido: bytes) -> list[tuple[str, list[list[str]]]]:
    """Hojas del libro, como texto (los valores, no las fórmulas)."""
    import openpyxl

    libro = openpyxl.load_workbook(io.BytesIO(contenido), data_only=True)
    hojas: list[tuple[str, list[list[str]]]] = []
    for hoja in libro.worksheets:
        filas = [
            ["" if c is None else str(c).strip() for c in fila]
            for fila in hoja.iter_rows(values_only=True)
        ]
        hojas.append((hoja.title, filas))
    return hojas


def _moneda_de_hoja(nombre: str, filas: list[list[str]]) -> str:
    """La moneda de la hoja: por su nombre (`DOLARES`) o por su celda `Moneda:`."""
    plano = _plano(nombre)
    if "DOLAR" in plano or "USD" in plano:
        return "USD"
    if "PESO" in plano or "COP" in plano:
        return "COP"
    for fila in filas[:15]:
        texto = _plano(" ".join(fila))
        if "MONEDA" in texto:
            if "DOLAR" in texto or "USD" in texto:
                return "USD"
            if "PESO" in texto or "COP" in texto:
                return "COP"
    return "COP"


def _valor_en_moneda(texto: str, moneda: str) -> Decimal | None:
    """En una hoja en dólares los importes usan coma decimal (`10,54`)."""
    formato = Formato.US if moneda == "USD" else Formato.CO
    unico = parsear_monto(quitar_duplicado(texto), formato)
    if unico is not None:
        return unico
    valores = buscar_montos(texto, formato)
    return valores[0] if valores else None


def movimientos_desde_hoja(filas: list[list[str]], moneda: str) -> list[MovimientoCrudo]:
    """Filas de una hoja de Excel: `Movimientos durante/antes del periodo`.

    El Excel de Amex (y casi todos) traen dos tablas con el mismo encabezado: la del
    periodo y la de movimientos anteriores. La segunda **no** se importa: es el capital
    de compras viejas y contarlo otra vez duplicaría el gasto.
    """
    movimientos: list[MovimientoCrudo] = []
    seccion: str | None = None
    columnas: dict[str, int] = {}

    for fila in filas:
        plano = _plano(" ".join(fila))
        if "MOVIMIENTOSDURANTEELPERIODO" in plano:
            seccion = "periodo"
            continue
        if "MOVIMIENTOSANTESDELPERIODO" in plano:
            seccion = "antes"
            continue
        if seccion is None:
            continue

        # Encabezado de la tabla: se mapean las columnas por nombre
        if "FECHA" in plano and ("MOVIMIENTO" in plano or "VALOR" in plano):
            for i, celda in enumerate(fila):
                campo = campo_de(celda)
                if campo:
                    columnas.setdefault(campo, i)
            continue
        if not columnas:
            continue

        fecha_txt = fila[columnas["fecha"]] if "fecha" in columnas and columnas["fecha"] < len(fila) else ""
        if not fecha_txt:
            continue
        fecha = _fecha_de(fecha_txt)
        valor_txt = (
            fila[columnas["valor"]] if "valor" in columnas and columnas["valor"] < len(fila) else ""
        )
        valor = _valor_en_moneda(valor_txt, moneda)
        if fecha is None or valor is None:
            continue

        descripcion = (
            fila[columnas["descripcion"]]
            if "descripcion" in columnas and columnas["descripcion"] < len(fila)
            else ""
        )
        movimiento = MovimientoCrudo(
            fecha=fecha,
            descripcion=descripcion.strip(),
            valor=valor,
            moneda=moneda,
            es_informativo=(seccion == "antes"),
        )
        for campo in ("cuota_mes", "valor_pendiente", "saldo"):
            if campo in columnas and columnas[campo] < len(fila):
                setattr(movimiento, campo, _valor_en_moneda(fila[columnas[campo]], moneda))
        if "tasa" in columnas and columnas["tasa"] < len(fila):
            movimiento.tasa_ea = _tasa_de(fila[columnas["tasa"]])
        if movimiento.tasa_ea is None and "tasa_mv" in columnas and columnas["tasa_mv"] < len(fila):
            # Excel de Amex: el interés anual está en su propia columna
            movimiento.tasa_ea = _tasa_de(fila[columnas["tasa_mv"]])
        if "cuotas" in columnas and columnas["cuotas"] < len(fila):
            cuotas = _cuotas_de(fila[columnas["cuotas"]])
            if cuotas:
                movimiento.cuotas_n, movimiento.cuotas_total = cuotas
        if "titular" in columnas and columnas["titular"] < len(fila):
            t = _plano(fila[columnas["titular"]])
            movimiento.titular = "T" if t.startswith("T") else ("A" if t.startswith("A") else None)
        movimientos.append(movimiento.cerrar())
    return movimientos


# --------------------------------------------------------------------------- #
# Entrada principal
# --------------------------------------------------------------------------- #


def formato_de(nombre: str, content_type: str | None = None) -> str:
    """Qué es el archivo. **Manda la extensión**: los navegadores mandan tipos raros.

    Un `extracto.pdf` con `content-type` de Excel (pasa cuando el sistema no lo conoce)
    tiene que leerse como PDF, no intentar abrirlo como libro.
    """
    bajo = (nombre or "").lower()
    if bajo.endswith((".xlsx", ".xlsm")):
        return "xlsx"
    if bajo.endswith(".csv"):
        return "csv"
    if bajo.endswith(".pdf"):
        return "pdf"
    tipo = (content_type or "").lower()
    if "spreadsheetml" in tipo or "ms-excel" in tipo:
        return "xlsx"
    if "csv" in tipo:
        return "csv"
    return "pdf"


def parsear(
    contenido: bytes, nombre: str, content_type: str | None = None, password: str | None = None
) -> tuple[ExtractoCrudo, str]:
    """Lee un extracto y devuelve `(extracto, texto_extraido)`."""
    formato = formato_de(nombre, content_type)

    if formato == "xlsx":
        extracto = ExtractoCrudo()
        partes: list[str] = []
        hojas = leer_excel(contenido)
        # La moneda principal manda para los totales declarados: se procesa primero.
        # Si el libro no trae pesos, la primera hoja es la principal.
        hojas.sort(key=lambda h: 0 if _moneda_de_hoja(h[0], h[1]) == "COP" else 1)
        for titulo, filas in hojas:
            moneda = _moneda_de_hoja(titulo, filas)
            texto_hoja = "\n".join(" ".join(f) for f in filas if any(f))
            partes.append(f"### {titulo}\n{texto_hoja}")
            # Los metadatos de la primera hoja son los del extracto; el detalle suma monedas
            metadatos(texto_hoja, extracto)
            extracto.movimientos.extend(movimientos_desde_hoja(filas, moneda))
        if extracto.moneda == "COP" and any(m.moneda != "COP" for m in extracto.movimientos):
            extracto.avisos.append(
                "El extracto trae movimientos en más de una moneda: se guardan por separado"
            )
        return extracto, "\n\n".join(partes)

    if formato == "csv":
        from .importacion import parsear_csv

        extracto = ExtractoCrudo(tipo="cuenta")
        for fila in parsear_csv(contenido.decode("utf-8", errors="replace")):
            extracto.movimientos.append(
                MovimientoCrudo(
                    fecha=date.fromisoformat(fila["fecha"]),
                    descripcion=fila["descripcion"] or "",
                    valor=Decimal(fila["monto"]) * (-1 if fila["tipo"] == "gasto" else 1),
                    moneda="COP",
                ).cerrar()
            )
        return extracto, contenido.decode("utf-8", errors="replace")

    texto, por_pagina = leer_pdf(contenido, password)
    extracto = ExtractoCrudo()
    metadatos(texto, extracto)
    # La tabla de movimientos suele empezar en una página y **continuar en las
    # siguientes sin repetir el encabezado**: se reutilizan las columnas ya deducidas y
    # se toman todos los renglones de la página (sin filtro de `y`).
    columnas_previas: tuple[float, list[tuple[str, float]], bool] | None = None
    for frags in por_pagina:
        encontrado = columnas_por_encabezado(frags)
        if encontrado is not None:
            columnas_previas = encontrado
        if columnas_previas is None:
            continue
        _, columnas, hacia_abajo = columnas_previas
        if encontrado is None:
            # Página de continuación: sin encabezado propio
            y_encabezado = float("-inf") if hacia_abajo else float("inf")
        else:
            y_encabezado = encontrado[0]
        extracto.movimientos.extend(
            movimientos_desde_filas(frags, y_encabezado, columnas, extracto.moneda, hacia_abajo)
        )
    if not extracto.movimientos:
        extracto.avisos.append(
            "No se reconoció la tabla de movimientos: revisa que sea un extracto y no otro documento"
        )
    return extracto, texto


def marcar_informativos(extracto: ExtractoCrudo) -> None:
    """Marca lo que no es gasto nuevo: movimientos fuera del periodo declarado.

    Los extractos de tarjeta listan el capital de compras anteriores (a veces de años
    atrás). Lo que cae dentro del periodo es lo nuevo; el resto es informativo.
    """
    if extracto.periodo_desde is None or extracto.periodo_hasta is None:
        return
    if extracto.periodo_desde > extracto.periodo_hasta:
        return  # un periodo invertido no sirve para decidir qué es de este mes
    for m in extracto.movimientos:
        if m.fecha is None:
            continue
        if m.fecha < extracto.periodo_desde or m.fecha > extracto.periodo_hasta:
            m.es_informativo = True


# --------------------------------------------------------------------------- #
# Conciliación
# --------------------------------------------------------------------------- #


def _check(nombre: str, calculado: Decimal | None, declarado: Decimal | None) -> dict:
    if calculado is None or declarado is None:
        return {
            "nombre": nombre,
            "calculado": None,
            "declarado": str(declarado) if declarado is not None else None,
            "ok": None,
        }
    diferencia = calculado - declarado
    return {
        "nombre": nombre,
        "calculado": str(calculado),
        "declarado": str(declarado),
        "diferencia": str(diferencia),
        "ok": abs(diferencia) <= TOLERANCIA_TOTAL,
    }


def conciliar(extracto: ExtractoCrudo) -> list[dict]:
    """Comprueba que el detalle cuadre con lo que el extracto declara.

    Compara **componentes** (no solo el total, que el banco redondea) y valida cada fila
    con el invariante de cuotas, que detecta un renglón mal leído aunque los totales
    cuadren.
    """
    # Solo la moneda principal del extracto: mezclar pesos y dólares en una suma no
    # significa nada (el extracto declara sus totales en su moneda)
    principal = extracto.moneda
    if extracto.abonos is not None and extracto.abonos < 0:
        extracto.abonos = -extracto.abonos  # `- Pagos ... $-1.103.790,03` es un positivo
    del_periodo = [
        m for m in extracto.movimientos if not m.es_informativo and m.moneda == principal
    ]
    # `compras` es lo que el extracto llama consumos: sin intereses, comisiones,
    # impuestos ni ajustes (esos van en sus propias líneas del desglose)
    compras = sum((m.valor for m in del_periodo if m.tipo == "compra" and m.valor > 0), CERO)
    # Algunos extractos (CMR) llaman «consumos del mes» al **capital facturado** del mes,
    # no al valor de las compras: ahí lo que se suma es lo que se factura de cada compra
    facturado = sum(
        (
            (m.cuota_mes or m.valor_pendiente or CERO)
            for m in del_periodo
            if m.tipo == "compra" and m.valor > 0
        ),
        CERO,
    )
    # Según el banco, un pago viene en negativo (Davivienda, Amex) o en positivo con
    # «PAGO» en la descripción (CMR): se cuentan los dos casos, por tipo.
    abonos = sum(
        (abs(m.valor) for m in del_periodo if m.tipo in ("pago", "ajuste")),
        CERO,
    )

    if extracto.compras_es_capital:
        checks = [
            _check("capital facturado del mes", facturado, extracto.compras),
            _check("pagos y abonos", abonos, extracto.abonos),
        ]
    else:
        checks = [
            _check("compras del periodo", compras, extracto.compras),
            _check("pagos y abonos", abonos, extracto.abonos),
        ]

    if extracto.saldo_anterior is not None and extracto.pago_total is not None:
        esperado = (
            extracto.saldo_anterior
            + (extracto.compras or CERO)
            + (extracto.intereses or CERO)
            + (extracto.intereses_mora or CERO)
            + (extracto.otros_cargos or CERO)
            - (extracto.abonos or CERO)
        )
        checks.append(_check("pago total", esperado, extracto.pago_total))

    if extracto.cupo_total is not None and extracto.cupo_disponible is not None:
        checks.append(_check("cupo utilizado", extracto.cupo_total - extracto.cupo_disponible, None))

    filas_dudosas = []
    validadas = 0
    con_cuotas = [m for m in extracto.movimientos if m.cuotas_total and m.cuotas_total > 1]
    for m in extracto.movimientos:
        if not m.cuotas_total or not m.cuotas_n or m.cuota_mes is None or m.valor_pendiente is None:
            continue
        validadas += 1
        faltantes = m.cuotas_total - m.cuotas_n
        if faltantes == 0:
            # La última cuota no puede dejar capital pendiente
            coherente = m.valor_pendiente <= TOLERANCIA_FILA
            esperado = CERO
        else:
            # OJO: el pendiente es **capital** y la cuota **incluye intereses**, así que la
            # cuota nunca es menor que el capital que reparte, y si es muchísimo mayor es
            # que una columna se leyó mal. Con 0% de interés coinciden exactamente (fue el
            # caso en 46 de 48 filas de Davivienda).
            capital_por_cuota = m.valor_pendiente / faltantes
            esperado = capital_por_cuota
            coherente = (
                capital_por_cuota * Decimal("0.98")
                <= m.cuota_mes
                <= capital_por_cuota * Decimal("2.5")
            )
        if not coherente:
            filas_dudosas.append(
                {
                    "fecha": m.fecha.isoformat() if m.fecha else None,
                    "descripcion": m.descripcion[:60],
                    "pendiente": str(m.valor_pendiente),
                    "cuota": str(m.cuota_mes),
                    "capital_por_cuota": str(esperado),
                }
            )
    if filas_dudosas:
        extracto.avisos.append(
            f"{len(filas_dudosas)} movimiento(s) no cuadran con su propia aritmética"
        )
    if con_cuotas and validadas == 0:
        # Un ✅ porque no se validó nada sería mentira: se dice que no hay datos
        extracto.avisos.append(
            "No se pudo comprobar la aritmética de los movimientos a cuotas: falta la "
            "columna de la cuota del mes en este extracto"
        )
    checks.append(
        {
            "nombre": "coherencia de las cuotas (la cuota cubre el capital que queda)",
            "calculado": str(validadas),
            "declarado": str(len(extracto.movimientos)),
            "ok": (not filas_dudosas) if validadas else None,
            "filas_dudosas": filas_dudosas[:10],
        }
    )
    return checks


def conciliacion_ok(checks: list[dict]) -> bool:
    """Una comprobación sin datos (`ok: None`) no invalida; una que falla, sí."""
    return all(c["ok"] is not False for c in checks)


def como_json(checks: list[dict]) -> str:
    return json.dumps(checks, ensure_ascii=False)
