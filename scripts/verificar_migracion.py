#!/usr/bin/env python
"""Compara los números de dos bases (el original y la copia restaurada).

Uso:
    python scripts/verificar_migracion.py postgresql+psycopg://.../finanzas postgresql+psycopg://.../finanzas_verificacion

Sale con código 1 si algo no cuadra, para que sirva en un `if` de un despliegue.
"""

from __future__ import annotations

import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, ".")

from app.verificacion import comparar, resumen_de  # noqa: E402


def resumen(url: str) -> dict:
    engine = create_engine(url)
    sf = sessionmaker(bind=engine)
    try:
        with sf.begin() as s:
            return resumen_de(s)
    finally:
        engine.dispose()


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    original, copia = resumen(sys.argv[1]), resumen(sys.argv[2])

    print("  Original:")
    for tabla, filas in original["tablas"].items():
        print(f"    {tabla:22} {filas}")
    print(f"    ingresos:  {original['dinero']['total_ingresos']:,.0f}")
    print(f"    gastos:    {original['dinero']['total_gastos']:,.0f}")
    print(f"    lecturas IA: {original['dinero']['lecturas_ia']}")

    problemas = comparar(original, copia)
    if not problemas:
        print("\n  ✅ La copia es fiel: los números cuadran.")
        return 0

    print(f"\n  ✗ {len(problemas)} diferencia(s):")
    for problema in problemas:
        print(f"    · {problema}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
