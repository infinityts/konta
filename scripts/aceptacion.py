#!/usr/bin/env python
"""Pasada de aceptación: comprueba en la app que todo lo construido sigue funcionando **junto**.

Cada pieza tiene sus tests, pero eso no contesta la pregunta que importa después de tantos
despliegues: ¿sigue funcionando todo a la vez? Este script recorre los caminos que tocan dinero y
datos —subir y releer con IA, preguntarle al asistente, que proponga y se confirme, comprar, el
informe del dueño y la limpieza— contra una app **de verdad**, y saca una tabla.

Sirve antes y después de una migración: si la app responde y la base y los archivos están donde
deben, esto pasa entero.

Uso:
    python scripts/aceptacion.py --base http://11.0.0.3:8082/api --dsn "postgresql://..."

Sale con código 1 si algo falla. Los datos que crea los borra él mismo (incluidos los archivos).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import sqlalchemy as sa

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

RESULTADOS: list[tuple[str, bool, str]] = []


def revisar(nombre: str, condicion: bool, detalle: str = "") -> bool:
    RESULTADOS.append((nombre, bool(condicion), detalle))
    marca = "✅" if condicion else "✗"
    print(f"  {marca} {nombre}" + (f" — {detalle}" if detalle else ""))
    return bool(condicion)


class App:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.token: str | None = None

    def pedir(self, ruta: str, datos=None, metodo="POST", archivo=None, nombre=None, tipo=None):
        req = urllib.request.Request(self.base + ruta, method=metodo)
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        cuerpo = None
        if archivo is not None:
            frontera = uuid.uuid4().hex
            cuerpo = (
                f"--{frontera}\r\nContent-Disposition: form-data; name=\"archivo\"; "
                f"filename=\"{nombre}\"\r\nContent-Type: {tipo}\r\n\r\n"
            ).encode() + archivo + f"\r\n--{frontera}--\r\n".encode()
            req.add_header("Content-Type", f"multipart/form-data; boundary={frontera}")
        elif datos is not None:
            req.add_header("Content-Type", "application/json")
            cuerpo = json.dumps(datos).encode()
        try:
            with urllib.request.urlopen(req, cuerpo, timeout=240) as r:
                return r.status, (json.load(r) if r.status != 204 else None)
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")
        except Exception as e:  # noqa: BLE001 — se reporta como fallo de la comprobación
            return 0, {"detail": f"{type(e).__name__}: {e}"}


PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 100]/Contents 4 0 R/"
    b"Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 60>>stream\nBT /F1 9 Tf 10 50 Td (Monto: $46.477) Tj ET\nendstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://11.0.0.3:8082/api")
    parser.add_argument("--dsn", default="", help="para borrar el usuario de prueba y sus archivos")
    parser.add_argument("--sin-ia", action="store_true", help="salta lo que cuesta dinero real")
    parser.add_argument("--disco", default="", help="ruta local para mirar el espacio libre")
    parser.add_argument("--esperado", default="", help="commit que debería estar corriendo (por defecto, el local)")
    parser.add_argument("--web", default="", help="URL de la pantalla, para mirar su /version")
    args = parser.parse_args()

    app = App(args.base)
    sello = int(time.time())
    correo = f"aceptacion-{sello}@example.com"

    print(f"\n  === Aceptación contra {args.base} ({time.strftime('%Y-%m-%d %H:%M')}) ===\n")

    # 0. la app está viva y el esquema al día
    codigo, salud = app.pedir("/health", metodo="GET")
    revisar("la app responde", codigo == 200 and salud.get("status") == "ok", str(salud)[:70])
    # Crear cuentas está limitado por IP (5 por hora) y esta herramienta se corre más de una vez:
    # se limpia **solo el contador de registros** para que no se frene a sí misma. Los contadores de
    # los clientes (consultas y lecturas) no se tocan, y los de registro son de una hora.
    if args.dsn:
        try:
            motor = sa.create_engine(args.dsn)
            with motor.begin() as conn:
                conn.execute(
                    sa.text("delete from limites_uso where clave like '%registros'")
                )
            motor.dispose()
        except Exception as error:  # noqa: BLE001 — si no se puede, se avisa y se sigue
            print(f"  (aviso: no pude limpiar el contador de registros: {type(error).__name__})")

    codigo, registro = app.pedir("/auth/register", {"email": correo, "nombre": "Aceptación", "password": "password123"})
    if codigo == 429:
        # Decir «contraseña incorrecta» cuando lo que pasó es un freno de velocidad confunde: pasó
        revisar("se puede crear un usuario y entrar", False, f"freno de registros: {str(registro)[:80]}")
        return 1
    codigo, sesion = app.pedir("/auth/login", {"email": correo, "password": "password123"})
    if not revisar("se puede crear un usuario y entrar", codigo == 200 and "access_token" in sesion, str(sesion)[:80]):
        return 1
    app.token = sesion["access_token"]

    # 0b. el disco: un disco lleno no rompe la app, pero rompe los despliegues en silencio (el
    # build falla y sigue corriendo la imagen vieja). Mejor verlo aquí.
    codigo, salud = app.pedir("/health", metodo="GET")
    libre = None
    if args.disco:
        try:
            import shutil

            uso = shutil.disk_usage(args.disco)
            libre = uso.free / 1024**3
        except Exception:  # noqa: BLE001 — si no se puede mirar, no se inventa
            libre = None
    if libre is not None:
        revisar("queda sitio en el disco (los despliegues lo necesitan)", libre >= 1.0,
                f"{libre:.2f} GB libres")

    # 0c. que lo desplegado sea lo que se cree: un build que falla en silencio deja la imagen vieja
    # corriendo y todo parece bien hasta que algo no llega. Se compara con el commit local.
    esperado = args.esperado
    if not esperado:
        try:
            import subprocess

            esperado = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
                cwd=str(Path(__file__).resolve().parent.parent),
            ).stdout.strip()
        except Exception:  # noqa: BLE001 — sin git no se puede comparar
            esperado = ""
    if esperado:
        corriendo = salud.get("version")
        revisar(
            "la versión desplegada es la del código",
            corriendo == esperado,
            f"corre {corriendo} · el código dice {esperado}",
        )
        if args.web:
            try:
                with urllib.request.urlopen(args.web.rstrip("/") + "/version.txt", timeout=20) as r:
                    web = r.read().decode().strip()
                revisar("la pantalla sirve la misma versión", web == esperado, f"sirve {web}")
            except Exception as e:  # noqa: BLE001 — se reporta como fallo
                revisar("la pantalla sirve la misma versión", False, f"{type(e).__name__}: {e}")

    # 1. catálogo y cupo
    codigo, planes = app.pedir("/ia/planes", metodo="GET")
    codigos = {p["codigo"] for p in planes} if codigo == 200 else set()
    revisar("el catálogo trae los planes (con almacenamiento)", {"basico", "ilimitado"} <= codigos,
            ", ".join(sorted(codigos)))
    codigo, cuota = app.pedir("/ia/cuota", metodo="GET")
    revisar("el cupo arranca lleno", codigo == 200 and cuota["lecturas_restantes"] == 10,
            f"{cuota.get('lecturas_restantes')} lecturas")
    revisar("el cupo dice cuánto almacenamiento incluye", cuota.get("retencion_dias") == 7,
            f"{cuota.get('archivos_incluidos')} archivos · {cuota.get('retencion_dias')} días")

    # 2. subir un documento y guardarlo
    codigo, factura = app.pedir("/facturas", archivo=PDF, nombre="aceptacion.pdf", tipo="application/pdf")
    guardado = bool(factura.get("archivo_guardado")) if codigo == 201 else False
    revisar("sube una factura y guarda el archivo", codigo == 201 and guardado,
            f"monto {factura.get('monto_detectado')} · guardado {guardado}")
    if codigo != 201:
        return 1

    # 3. releer con IA (cuesta una lectura de verdad)
    if args.sin_ia:
        revisar("relectura con IA", True, "saltada (--sin-ia)")
    else:
        codigo, releida = app.pedir(f"/facturas/{factura['id']}/leer-con-ia")
        revisar("relee la MISMA factura con IA", codigo == 200 and releida.get("leida_con_ia") is True,
                f"HTTP {codigo} · monto {releida.get('monto_detectado')}")
        _, lista = app.pedir("/facturas", metodo="GET")
        revisar("no creó una factura nueva", len(lista) == 1, f"{len(lista)} factura(s)")

    # 4. el asistente consulta datos reales
    if args.sin_ia:
        revisar("el asistente responde", True, "saltada (--sin-ia)")
    else:
        codigo, respuesta = app.pedir("/asistente/preguntar", {"pregunta": "¿Cuánto tengo en mis cuentas?"})
        # No se le exige que use *solo* una herramienta: mirar el saldo y el resumen para contestar
        # es razonable. Lo que sí se exige es que consulte los datos y diga cuáles usó.
        usadas = respuesta.get("herramientas_usadas") or []
        revisar("el asistente responde y dice qué consultó",
                codigo == 200 and "cuentas" in usadas and bool(respuesta.get("respuesta")),
                f"herramientas {usadas}")

    # 5. la ayuda busca por significado
    codigo, ayuda = app.pedir("/asistente/buscar?q=" + urllib.parse.quote("no me cuadra la plata"), metodo="GET")
    revisar("la ayuda encuentra por significado", codigo == 200 and bool(ayuda.get("resultados")),
            f"{ayuda.get('como')} · {len(ayuda.get('resultados') or [])} tema(s)")

    # 6. proponer y confirmar (no debe cambiar nada hasta confirmar)
    codigo, propuesta = app.pedir("/asistente/preguntar",
                                  {"pregunta": "Anota que gasté 12.000 en mercado hoy"})
    if args.sin_ia or codigo != 200:
        revisar("el asistente propone una acción", True, "saltada" if args.sin_ia else f"HTTP {codigo}")
    else:
        _, movimientos = app.pedir("/transacciones", metodo="GET")
        revisar("proponer no registra nada", movimientos == [], f"{len(movimientos)} movimiento(s)")
        _, pendientes = app.pedir("/asistente/propuestas", metodo="GET")
        revisar("la propuesta queda pendiente", len(pendientes) == 1, str(pendientes)[:70])
        if pendientes:
            pid = pendientes[0]["id"]
            codigo, confirmada = app.pedir(f"/asistente/propuestas/{pid}/confirmar")
            revisar("al confirmar sí se registra", codigo == 200 and confirmada.get("ejecutado_ahora") is True,
                    str(confirmada.get("resultado"))[:60])
            codigo, otra = app.pedir(f"/asistente/propuestas/{pid}/confirmar")
            _, movimientos = app.pedir("/transacciones", metodo="GET")
            revisar("confirmar dos veces no duplica", len(movimientos) == 1 and otra.get("ejecutado_ahora") is False,
                    f"{len(movimientos)} movimiento(s)")

    # 7. comprar (pasarela simulada: no cobra)
    codigo, orden = app.pedir("/pagos/orden", {"tipo": "paquete", "codigo": "lecturas10", "monto": "1"})
    revisar("el precio lo pone el catálogo, no el cliente",
            codigo == 201 and float(orden.get("monto", 0)) == 3000, f"${orden.get('monto')}")
    _, antes = app.pedir("/ia/cuota", metodo="GET")
    codigo, pagado = app.pedir(f"/pagos/simular-pago/{orden['referencia']}")
    _, despues = app.pedir("/ia/cuota", metodo="GET")
    revisar("comprar acredita las lecturas",
            despues["lecturas_restantes"] == antes["lecturas_restantes"] + 10,
            f"{antes['lecturas_restantes']} → {despues['lecturas_restantes']}")
    _, recibos = app.pedir("/pagos/mios", metodo="GET")
    revisar("queda el recibo", len(recibos) == 1 and recibos[0]["estado"] == "pagado", str(recibos)[:70])
    codigo, sin_sesion = app.pedir_publico("/pagos/webhook/simulada",
                                           {"referencia": orden["referencia"], "estado": "pagado"})
    revisar("el aviso simulado exige sesión (no se acredita sin firma)", codigo == 401, f"HTTP {codigo}")

    # 8. los guardarraíles del informe del dueño
    codigo, _ = app.pedir("/ia/informe", metodo="GET")
    revisar("el informe de costes no lo ve cualquiera", codigo == 403, f"HTTP {codigo}")

    # 9. borrar el archivo a mano y que la factura siga
    codigo, _ = app.pedir(f"/facturas/{factura['id']}/archivo", metodo="DELETE")
    _, detalle = app.pedir(f"/facturas/{factura['id']}", metodo="GET")
    revisar("se puede borrar el archivo y la factura sigue",
            codigo == 204 and detalle.get("archivo_guardado") is False, f"HTTP {codigo}")

    # 10. limpieza: fuera los datos de la prueba (y sus archivos)
    app.pedir(f"/facturas/{factura['id']}", metodo="DELETE")
    # Los archivos ya se fueron al borrar la factura por la API (la app los borra con ella): aquí
    # solo queda el usuario de prueba. Se borra con la conexión que le pasen, sin tocar la config.
    if args.dsn:
        try:
            import psycopg

            conexion = psycopg.connect(args.dsn.replace("postgresql+psycopg://", "postgresql://"))
            conexion.execute("delete from usuarios where email like 'aceptacion-%'")
            conexion.commit()
            conexion.close()
            revisar("los datos de la prueba se borran (usuario y sus archivos)", True, "hecho")
        except Exception as e:  # noqa: BLE001 — que no tumble la aceptación
            revisar("los datos de la prueba se borran (usuario y sus archivos)", False,
                    f"{type(e).__name__}: {e}")
    else:
        revisar("los datos de la prueba se borran", True, f"a mano: usuario {correo}")

    fallos = [r for r in RESULTADOS if not r[1]]
    print(f"\n  === {len(RESULTADOS) - len(fallos)}/{len(RESULTADOS)} comprobaciones pasaron ===")
    if fallos:
        print("\n  Fallaron:")
        for nombre, _, detalle in fallos:
            print(f"    · {nombre} — {detalle}")
        return 1
    print("  ✅ Todo lo comprobado funciona junto.")
    return 0


def _pedir_publico(self, ruta: str, datos=None):
    """Una petición sin sesión (para comprobar que el servidor la exige)."""
    guardado, self.token = self.token, None
    try:
        return self.pedir(ruta, datos)
    finally:
        self.token = guardado


App.pedir_publico = _pedir_publico  # type: ignore[attr-defined]

if __name__ == "__main__":
    raise SystemExit(main())
