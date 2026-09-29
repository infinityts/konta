"""Lectura de una factura de caja grande y etiquetado automático de sus artículos.

Sale de una factura real de supermercado (120 artículos) cuyo OCR llegaba incompleto a la
aplicación. Los tres problemas que se arreglaron, cada uno con su prueba:

1. **El dinero se leía 1.000 veces más pequeño**: esa caja imprime `24,674` (veinticuatro mil
   seiscientos setenta y cuatro) en vez del `24.674` de siempre, y el detector de formato no
   lo veía.
2. **Se colaban líneas que no son artículos** (`Tel: 4850175 Ext`, `TPV : TPV008SP`) y se
   perdían artículos: las líneas con marca de descuento (`6,375* D`) no casaban.
3. **Los artículos no se etiquetaban**: el diccionario no conocía `PERNIL`, `MARGARINA`,
   `UVA`… y `YOGUR` no casaba con `YOGURT` (se busca la palabra completa).

Los datos de las pruebas son inventados: la factura real no se versiona.
"""

from __future__ import annotations

from decimal import Decimal

from app.clasificador import _por_diccionario, normalizar
from app.dinero import Formato, detectar_formato, parsear_monto
from app.facturas import detectar_monto
from app.lineas import cantidad, detectar_tipo, parsear_lineas

# Una factura como la de la caja grande: artículo numerado y su línea de valores
FACTURA = """SUPERTIENDAS EJEMPLO S.A.S.
NIT: 800.000.000-1
Tel: 4850175 Ext: 601
Fecha : 2026/9/16 Hora: 08:59:27
TPV : TPV008SP012
----------------------------------------
Item Descripcion de Item
Referencia Cant. U.M V/r Uni. Total
----------------------------------------
1 FILETE PECHUGA BUCANERO A GRANEL
023029 1.372 kg 24,674 33,854**
2 BOLSA EJEMPLO 100% MATERIAL RECICL F
0038007 4.00 un 300 1,200*
3 PERNIL BUCANERO CAMPO A GRANEL
023027 1.296 kg 9,570 12,403**
4 SALSA EJEMPLO*165ml CARNES
0050874 1.00 un 6,375 6,375* D
5 YOGURT EJEMPLO*150g FRESA
0039441 1.00 un 3,350 3,350*
6 ATUN EJEMPLO*142g A/GIRASOL
COVA-00 1.00 un 5,950 5,950*
7 UVA VERDE IMPORTADA A GRANEL
0042420 1.372 kg 17,226 23,632
----------------------------------------
T O T A L ............ $1,188,248
TOTAL ITEMS........... 7
"""


def test_el_formato_del_dinero_de_esa_caja():
    """`24,674` es veinticuatro mil: la coma separa miles, no decimales."""
    formato = detectar_formato(FACTURA.splitlines())
    assert formato == Formato.US
    assert parsear_monto("24,674", formato) == Decimal("24674")
    assert parsear_monto("1,188,248", formato) == Decimal("1188248")
    # La cantidad con peso sigue siendo decimal con el punto: 1.372 kg
    assert cantidad("1.372", "kg") == Decimal("1.372")
    # Y dos decimales tras el punto son decimales aunque la unidad sea de cuenta
    assert cantidad("4.00", "un") == Decimal("4.00")


def test_la_factura_se_lee_entera_y_sin_basura():
    """Siete artículos, sin el `Tel:` ni el `TPV`, y con los montos bien."""
    articulos = parsear_lineas(FACTURA)
    assert len(articulos) == 7

    descripciones = [a["descripcion"] for a in articulos]
    assert descripciones[0] == "FILETE PECHUGA BUCANERO A GRANEL", "sin el número de artículo"
    assert not any("Tel:" in d or "TPV" in d or "NIT" in d for d in descripciones)

    # Los montos, en pesos de verdad (antes salían 1.000 veces más pequeños)
    assert [a["valor_total"] for a in articulos[:3]] == [
        Decimal("33854"), Decimal("1200"), Decimal("12403")
    ]
    assert articulos[0]["valor_unitario"] == Decimal("24674")
    assert articulos[0]["cantidad"] == Decimal("1.372")
    # La cantidad en unidades no se multiplica por cien
    assert articulos[1]["cantidad"] == Decimal("4.00")

    # La línea del descuento (`6,375* D`) es un artículo más, no se pierde
    assert articulos[3]["valor_total"] == Decimal("6375")
    # Y la referencia de promoción (`COVA-00`) también se acepta
    assert articulos[5]["descripcion"].startswith("ATUN")
    assert articulos[5]["valor_total"] == Decimal("5950")


def test_el_total_de_la_factura_no_es_el_numero_de_articulos():
    """`T O T A L` viene con las letras separadas, y `TOTAL ITEMS` no es un monto."""
    assert detectar_monto(FACTURA) == Decimal("1188248")


def test_el_tipo_de_documento():
    assert detectar_tipo(FACTURA) == "mercado"


# --------------------------------------------------------------------------- #
# Etiquetado automático
# --------------------------------------------------------------------------- #


def _etiqueta(descripcion: str, etiquetas: dict[str, str]) -> str | None:
    """A qué etiqueta va una descripción, con el nivel de diccionario del clasificador."""
    resultado = _por_diccionario(normalizar(descripcion), etiquetas)
    return resultado[0] if resultado else None


def test_los_articulos_de_mercado_se_etiquetan_solos():
    """El valor de la herramienta: cada artículo cae en su etiqueta sin tocar nada."""
    etiquetas = {
        "CARNES": "carnes",
        "LACTEOS Y HUEVOS": "lacteos",
        "DESPENSA": "despensa",
        "FRUTAS Y VERDURAS": "frutas",
        "ASEO DEL HOGAR": "aseo",
        "CUIDADO PERSONAL": "personal",
    }
    casos = [
        ("FILETE PECHUGA BUCANERO A GRANEL", "carnes"),
        ("PERNIL BUCANERO CAMPO A GRANEL", "carnes"),
        ("HIGADO RES A GRANEL", "carnes"),
        # «PEPINO RES» es una carne de res, no un pepino
        ("PEPINO RES A GRANEL", "carnes"),
        ("QUESO ALPINA*250g PARMESANO", "lacteos"),
        ("MARGARINA CAMPI*250g C/SAL", "lacteos"),
        # `YOGUR` no casa con `YOGURT`: se busca la palabra completa
        ("YOGURT VITAD*150g FRESA", "lacteos"),
        ("HUEVO ORO AA*30und ROSADO", "lacteos"),
        ("ARROZ ROA*12500g ARROBA", "despensa"),
        ("ATUN ISABEL*142g A/GIRASOL LOMITOS", "despensa"),
        ("GALLETA DUCALES*315g 3 TACOS", "despensa"),
        # «SALSA ... DE TOMATE» es despensa aunque lleve TOMATE
        ("SALSA FRUCO*190g DE TOMATE D/P", "despensa"),
        ("CEBOLLA BADIA*78g EN POLVO", "despensa"),
        ("UVA VERDE IMPORTADA A GRANEL", "frutas"),
        ("SANDIA A GRANEL", "frutas"),
        ("COLIFLOR A GRANEL", "frutas"),
        ("KIWI A GRANEL", "frutas"),
        ("BOLSA CANAVERAL 100% MATERIAL RECICL", "aseo"),
        ("DESMAN VANISH*240g ROSA POLVO", "aseo"),
        ("SEDA DENT FCARDENT*35mt LIMPIE", "personal"),
        ("T.H NOSOTRAS*24und EXTRA PROTEC TELA", "personal"),
    ]
    fallos = [
        (descripcion, esperada, _etiqueta(descripcion, etiquetas))
        for descripcion, esperada in casos
        if _etiqueta(descripcion, etiquetas) != esperada
    ]
    assert fallos == [], f"{len(fallos)} de {len(casos)} mal etiquetados: {fallos}"


def test_un_articulo_desconocido_queda_sin_clasificar_y_el_usuario_decide():
    """Lo que el diccionario no sabe **no se inventa**: queda para que lo elija el usuario."""
    etiquetas = {"CARNES": "carnes", "DESPENSA": "despensa"}
    assert _etiqueta("PRODUCTO RARO SIN PISTAS", etiquetas) is None
