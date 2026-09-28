"""Migraciones que **mueven datos**, sobre una base con filas.

El resto de la suite migra una base vacía, y eso no prueba nada de las migraciones
de datos: la `0013` limpia duplicados entre hermanos y la `0014` convierte las
subcategorías en etiquetas repuntando transacciones, presupuestos, suscripciones e
ingresos recurrentes. Son justo las que pueden romper al desplegar sobre una base
real, y hasta ahora solo se habían probado con las tablas vacías.

El test crea su propia base (`konta_migraciones`) y reproduce **el camino real de
un despliegue por versiones**:

    0012  -> datos de la versión vieja (etiquetas sueltas, categorías con hijos)
    0013  -> añade `etiquetas.categoria_id` y fusiona los duplicados
    (aquí la app en producción re-categoriza las etiquetas: es el paso que el
     usuario hace entre la v1.7 y la v1.8)
    head  -> 0014 convierte las subcategorías en etiquetas y borra lo que sigue
             sin categoría (comportamiento documentado en el CHANGELOG v1.8)

De ahí sale también el aviso de despliegue que documenta este test: una etiqueta
que llegue a la `0014` **sin `categoria_id` se borra**.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

TEST_URL = os.environ.get("FINANZAS_TEST_DATABASE_URL") or os.environ.get(
    "FINANZAS_DATABASE_URL"
)
NOMBRE_BD = "konta_migraciones"
ANTES = "0012"  # última revisión previa a las migraciones de datos
ENTRE = "0013"  # ya con etiquetas.categoria_id, antes del árbol único

pytestmark = pytest.mark.skipif(
    not TEST_URL, reason="FINANZAS_TEST_DATABASE_URL no definida"
)


def _u(n: int) -> uuid.UUID:
    """UUID determinista: así el dedupe (que conserva el id menor) es predecible."""
    return uuid.UUID(int=n)


# Datos del escenario
USUARIO = _u(1)
RAIZ = _u(10)  # Vivienda (se conserva)
RAIZ_DUP = _u(11)  # VIVIENDA (duplicado: se fusiona en la anterior)
SUB = _u(12)  # Servicios, hija de Vivienda -> pasa a etiqueta
ETQ = _u(20)  # etiqueta "Internet" (se conserva y el usuario la re-categoriza)
ETQ_DUP = _u(21)  # "internet" duplicada -> se fusiona en la anterior
ETQ_HUERFANA = _u(22)  # nadie la re-categoriza -> se borra (documentado)
ETQ_HIJA = _u(23)  # subetiqueta de ETQ, re-categorizada también
TX_SUB = _u(30)  # gasto en la subcategoría
TX_DUP = _u(31)  # gasto en la categoría duplicada
TX_ETQ = _u(32)  # gasto con la etiqueta duplicada
TX_SIN = _u(33)  # gasto sin categoría ni etiqueta (no debe tocarse)
PRESUPUESTO = _u(40)
SUSCRIPCION = _u(41)
INGRESO = _u(42)


@pytest.fixture(scope="function")
def url_migraciones():
    """Crea la base de trabajo y la borra al terminar."""
    base = make_url(TEST_URL)
    destino = base.set(database=NOMBRE_BD)
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{NOMBRE_BD}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{NOMBRE_BD}"'))
    except Exception as exc:  # sin permiso para crear bases
        admin.dispose()
        pytest.skip(f"No se pudo crear la base de pruebas: {exc}")
    yield destino.render_as_string(hide_password=False)
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{NOMBRE_BD}" WITH (FORCE)'))
    admin.dispose()


def _migrar(url: str, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, revision)


def _revision_actual(conn) -> str:
    return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _insertar_datos(url: str) -> None:
    """Inserta el escenario con SQL, porque el esquema de 0012 no es el de los modelos."""
    motor = create_engine(url)
    with motor.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO usuarios (id, email, nombre, password_hash) "
                "VALUES (:id, 'viejo@x.com', 'Viejo', 'x')"
            ),
            {"id": USUARIO},
        )
        # Dos raíces con el mismo nombre (sin distinguir mayúsculas) y una subcategoría
        for cid, nombre, padre in (
            (RAIZ, "Vivienda", None),
            (RAIZ_DUP, "VIVIENDA", None),
            (SUB, "Servicios", RAIZ),
        ):
            conn.execute(
                text(
                    "INSERT INTO categorias (id, usuario_id, nombre, tipo, padre_id) "
                    "VALUES (:id, :u, :n, 'gasto', :p)"
                ),
                {"id": cid, "u": USUARIO, "n": nombre, "p": padre},
            )
        for eid, nombre, padre in (
            (ETQ, "Internet", None),
            (ETQ_DUP, "internet", None),
            (ETQ_HUERFANA, "Sin casa", None),  # quedará sin categoría
            (ETQ_HIJA, "Fibra", ETQ),
        ):
            conn.execute(
                text(
                    "INSERT INTO etiquetas (id, usuario_id, nombre, padre_id, creada_en) "
                    "VALUES (:id, :u, :n, :p, now())"
                ),
                {"id": eid, "u": USUARIO, "n": nombre, "p": padre},
            )

        def gasto(tx_id, categoria, etiqueta, descripcion):
            conn.execute(
                text(
                    "INSERT INTO transacciones (id, usuario_id, tipo, monto, fecha, "
                    "descripcion, categoria_id, etiqueta_id) "
                    "VALUES (:id, :u, 'gasto', 10000, '2026-08-15', :d, :c, :e)"
                ),
                {
                    "id": tx_id,
                    "u": USUARIO,
                    "d": descripcion,
                    "c": categoria,
                    "e": etiqueta,
                },
            )

        gasto(TX_SUB, SUB, None, "internet del mes")
        gasto(TX_DUP, RAIZ_DUP, None, "arriendo")
        gasto(TX_ETQ, None, ETQ_DUP, "otra cosa")
        gasto(TX_SIN, None, None, "sin clasificar")

        conn.execute(
            text(
                "INSERT INTO presupuestos (id, usuario_id, categoria_id, monto_limite) "
                "VALUES (:id, :u, :c, 500000)"
            ),
            {"id": PRESUPUESTO, "u": USUARIO, "c": SUB},
        )
        conn.execute(
            text(
                "INSERT INTO suscripciones (id, usuario_id, nombre, monto, categoria_id) "
                "VALUES (:id, :u, 'Internet', 90000, :c)"
            ),
            {"id": SUSCRIPCION, "u": USUARIO, "c": SUB},
        )
        conn.execute(
            text(
                "INSERT INTO ingresos_recurrentes "
                "(id, usuario_id, nombre, monto, periodicidad, proxima_ejecucion, categoria_id) "
                "VALUES (:id, :u, 'Sueldo', 1000000, 'mensual', '2026-09-01', :c)"
            ),
            {"id": INGRESO, "u": USUARIO, "c": SUB},
        )
    motor.dispose()


def test_migraciones_de_datos_sobre_una_base_con_filas(url_migraciones):
    _migrar(url_migraciones, ANTES)
    _insertar_datos(url_migraciones)
    _migrar(url_migraciones, ENTRE)

    # Paso intermedio del despliegue real: con la app de la v1.7 en producción, el
    # usuario re-categoriza sus etiquetas. Las que se queden sin categoría las borra
    # la 0014 (comportamiento documentado en el CHANGELOG v1.8).
    motor = create_engine(url_migraciones)
    with motor.begin() as conn:
        # La 0013 ya fusionó la etiqueta duplicada y repuntó el movimiento
        assert (
            conn.execute(
                text("SELECT count(*) FROM etiquetas WHERE id = :id"), {"id": ETQ_DUP}
            ).scalar_one()
            == 0
        ), "la 0013 debía fusionar la etiqueta duplicada"
        assert (
            conn.execute(
                text("SELECT etiqueta_id FROM transacciones WHERE id = :id"), {"id": TX_ETQ}
            ).scalar_one()
            == ETQ
        ), "el movimiento debía quedar en la etiqueta que se conservó"

        # Se re-categorizan la que sobrevive y su subetiqueta; la huérfana no
        conn.execute(
            text("UPDATE etiquetas SET categoria_id = :c WHERE id IN (:a, :b)"),
            {"c": RAIZ, "a": ETQ, "b": ETQ_HIJA},
        )
    motor.dispose()

    _migrar(url_migraciones, "head")

    motor = create_engine(url_migraciones)
    with motor.connect() as conn:
        # --- el esquema llegó al final ---
        head = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert head != ANTES and head != ENTRE
        columnas = {
            fila[0]
            for fila in conn.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'categorias'"
                )
            )
        }
        assert "padre_id" not in columnas, "la 0014 debe eliminar categorias.padre_id"
        tablas = {
            fila[0]
            for fila in conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            )
        }
        assert {"polizas", "beneficiarios", "poliza_asegurados"} <= tablas

        # --- no se perdió ninguna transacción ---
        total_tx = conn.execute(
            text("SELECT count(*) FROM transacciones WHERE usuario_id = :u"), {"u": USUARIO}
        ).scalar_one()
        assert total_tx == 4

        # --- las categorías quedan como raíces, sin duplicados ---
        categorias = conn.execute(
            text("SELECT id, nombre FROM categorias WHERE usuario_id = :u"), {"u": USUARIO}
        ).all()
        assert len(categorias) == 1, f"debe quedar solo la raíz: {categorias}"
        assert categorias[0].id == RAIZ  # se conserva el id menor
        assert categorias[0].nombre == "Vivienda"

        # --- la subcategoría se convirtió en etiqueta DENTRO de su categoría ---
        etiquetas = conn.execute(
            text("SELECT id, nombre, categoria_id, padre_id FROM etiquetas WHERE usuario_id = :u"),
            {"u": USUARIO},
        ).all()
        por_nombre = {e.nombre: e for e in etiquetas}
        assert "Servicios" in por_nombre, f"falta la etiqueta de la subcategoría: {etiquetas}"
        assert por_nombre["Servicios"].categoria_id == RAIZ
        assert por_nombre["Servicios"].padre_id is None
        # Las re-categorizadas sobreviven en su sitio, con su subetiqueta
        assert por_nombre["Internet"].id == ETQ
        assert por_nombre["Internet"].categoria_id == RAIZ
        assert por_nombre["Fibra"].padre_id == ETQ
        assert "internet" not in por_nombre, "el duplicado no debe reaparecer"
        # La que nadie re-categorizó se borra: es el aviso de despliegue de la 0014
        assert "Sin casa" not in por_nombre

        # --- las referencias se repuntaron ---
        filas = {
            fila.id: fila
            for fila in conn.execute(
                text(
                    "SELECT id, categoria_id, etiqueta_id FROM transacciones "
                    "WHERE usuario_id = :u"
                ),
                {"u": USUARIO},
            )
        }
        # La subcategoría -> raíz + etiqueta equivalente
        assert filas[TX_SUB].categoria_id == RAIZ
        assert filas[TX_SUB].etiqueta_id == por_nombre["Servicios"].id
        # La categoría duplicada -> la que se conservó
        assert filas[TX_DUP].categoria_id == RAIZ
        # La etiqueta duplicada -> la que se conservó
        assert filas[TX_ETQ].etiqueta_id == ETQ
        # El movimiento sin clasificar no se toca
        assert filas[TX_SIN].categoria_id is None
        assert filas[TX_SIN].etiqueta_id is None

        # El resto de referencias también pasan a la raíz
        for tabla, id_ in (
            ("presupuestos", PRESUPUESTO),
            ("suscripciones", SUSCRIPCION),
            ("ingresos_recurrentes", INGRESO),
        ):
            categoria = conn.execute(
                text(f"SELECT categoria_id FROM {tabla} WHERE id = :id"), {"id": id_}
            ).scalar_one()
            assert categoria == RAIZ, f"{tabla} debía quedar en la raíz"

    # --- la unicidad entre hermanos ya se aplica ---
    with motor.begin() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO categorias (id, usuario_id, nombre, tipo) "
                    "VALUES (:id, :u, 'vivienda', 'gasto')"
                ),
                {"id": _u(99), "u": USUARIO},
            )
    motor.dispose()


def test_0021_fusiona_los_duplicados_que_dejo_la_restriccion_perdida(url_migraciones):
    """La 0021 no puede limitarse a crear el índice: puede haber duplicados ya.

    Entre la 0014 (que se llevó el índice sin querer) y la 0021, la base no tenía
    ninguna garantía de unicidad de categorías. Si alguien creó duplicados en ese
    hueco, crear el índice a secas fallaría al desplegar. Este test reproduce esa
    base y comprueba que se fusionan y se repuntan las referencias.
    """
    _migrar(url_migraciones, "0020")

    primera, duplicada = _u(50), _u(51)
    tx, poliza = _u(60), _u(61)
    motor = create_engine(url_migraciones)
    with motor.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO usuarios (id, email, nombre, password_hash) "
                "VALUES (:id, 'dup@x.com', 'Dup', 'x')"
            ),
            {"id": USUARIO},
        )
        for cid, nombre in ((primera, "Vivienda"), (duplicada, "vivienda")):
            conn.execute(
                text(
                    "INSERT INTO categorias (id, usuario_id, nombre, tipo) "
                    "VALUES (:id, :u, :n, 'gasto')"
                ),
                {"id": cid, "u": USUARIO, "n": nombre},
            )
        conn.execute(
            text(
                "INSERT INTO transacciones (id, usuario_id, tipo, monto, fecha, categoria_id) "
                "VALUES (:id, :u, 'gasto', 1000, '2026-09-01', :c)"
            ),
            {"id": tx, "u": USUARIO, "c": duplicada},
        )
        conn.execute(
            text(
                "INSERT INTO polizas (id, usuario_id, tipo, aseguradora, prima, categoria_id) "
                "VALUES (:id, :u, 'hogar', 'Sura', 100000, :c)"
            ),
            {"id": poliza, "u": USUARIO, "c": duplicada},
        )
    motor.dispose()

    _migrar(url_migraciones, "head")

    with motor.connect() as conn:
        categorias = conn.execute(
            text("SELECT id FROM categorias WHERE usuario_id = :u"), {"u": USUARIO}
        ).all()
        assert len(categorias) == 1, f"los duplicados debían fusionarse: {categorias}"
        assert categorias[0].id == primera  # se conserva el id menor
        # Y las referencias al duplicado apuntan a la superviviente
        assert (
            conn.execute(
                text("SELECT categoria_id FROM transacciones WHERE id = :id"), {"id": tx}
            ).scalar_one()
            == primera
        )
        assert (
            conn.execute(
                text("SELECT categoria_id FROM polizas WHERE id = :id"), {"id": poliza}
            ).scalar_one()
            == primera
        )
    motor.dispose()
