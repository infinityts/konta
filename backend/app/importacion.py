"""Importación de estados de cuenta bancarios en CSV.

Detecta el delimitador y las columnas (fecha / descripción / monto) de forma
flexible, y normaliza cada fila a una transacción.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def _detectar_delimitador(texto: str) -> str:
    muestra = texto[:2000]
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
    except csv.Error:
        conteo = {d: muestra.count(d) for d in ",;\t|"}
        return max(conteo, key=conteo.get)


def _parse_monto(texto: str) -> Decimal | None:
    s = (texto or "").strip().replace("$", "").replace(" ", "")
    if not s:
        return None
    negativo = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()")
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = Decimal(s)
    except InvalidOperation:
        return None
    return -v if negativo else v


def _parse_fecha(texto: str) -> date | None:
    s = (texto or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%Y/%m/%d", "%m/%d/%Y"):
        try:
            # Solo se usa la parte de fecha: no hay hora ni zona que perder
            return datetime.strptime(s, fmt).date()  # noqa: DTZ007
        except ValueError:
            continue
    return None


def _indice(encabezados: list[str], nombres: list[str]) -> int | None:
    for i, h in enumerate(encabezados):
        if any(n in h for n in nombres):
            return i
    return None


def parsear_csv(contenido: str, tipo_default: str = "gasto") -> list[dict]:
    delim = _detectar_delimitador(contenido)
    filas = [
        f
        for f in csv.reader(io.StringIO(contenido), delimiter=delim)
        if any(c.strip() for c in f)
    ]
    if not filas:
        return []

    primera = [c.strip().lower() for c in filas[0]]
    tiene_header = any(
        re.search(r"fecha|date|descrip|concepto|detalle|monto|valor|importe|amount|cargo|abono", c)
        for c in primera
    )

    if tiene_header:
        i_fecha = _indice(primera, ["fecha", "date"])
        i_desc = _indice(primera, ["descrip", "concepto", "detalle", "description"])
        i_monto = _indice(primera, ["monto", "valor", "importe", "amount", "cargo", "abono", "debito", "credito"])
        datos = filas[1:]
    else:
        i_fecha, i_desc, i_monto = 0, 1, 2
        datos = filas

    if i_fecha is None or i_monto is None:
        return []

    crudos: list[tuple[date, str, Decimal]] = []
    for fila in datos:
        try:
            fecha = _parse_fecha(fila[i_fecha])
            monto = _parse_monto(fila[i_monto])
        except IndexError:
            continue
        if fecha is None or monto is None:
            continue
        desc = fila[i_desc].strip() if i_desc is not None and i_desc < len(fila) else ""
        crudos.append((fecha, desc, monto))

    # Si hay signos (negativos) los usamos; si no, aplicamos el tipo por defecto
    hubo_negativo = any(m < 0 for _, _, m in crudos)
    return [
        {
            "fecha": fecha.isoformat(),
            "descripcion": desc[:255] or None,
            "monto": str(abs(monto)),
            "tipo": ("gasto" if monto < 0 else "ingreso") if hubo_negativo else tipo_default,
        }
        for fecha, desc, monto in crudos
    ]
