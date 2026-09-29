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

from app.clasificador import DICCIONARIO, _por_diccionario, normalizar, sin_acentos_upper
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


# --------------------------------------------------------------------------- #
# Los productos reales de una cuenta que salían sin clasificar
# --------------------------------------------------------------------------- #

# Estas son las 16 descripciones que quedaron «sin clasificar» en una cuenta real, más
# las que estaban mal puestas. La causa no era el diccionario: a esa cuenta le faltaban
# las etiquetas `Lácteos y huevos` y `Cuidado personal`, y el diccionario empareja contra
# **nombres de etiquetas**. Con las etiquetas completas, todas caen donde deben.
PRODUCTOS_REALES: tuple[tuple[str, str], ...] = (
    ("CEP COLGATE*4und SUPER FLEXI", "Cuidado personal"),
    ("CREMA DE LECH ALQUERIA*170g CULINARIA", "Lácteos y huevos"),
    ("CREMA DE LECH ALQUERIA*180g SEMIENTER", "Lácteos y huevos"),
    ("DESOD REXONA*150ml*2und CLIN EXPERT W", "Cuidado personal"),
    ("HUEVO ORO AA*30und ROSADO CAMPESINO T", "Lácteos y huevos"),
    ("LECHE ALPINA*1000ml*4und DESLAC TETRA", "Lácteos y huevos"),
    ("QUESO ALPINA*200g CREMOSINO", "Lácteos y huevos"),
    ("QUESO ALPINA*240g MOZAREL TAJADO", "Lácteos y huevos"),
    ("QUESO ALPINA*250g PARMESANO", "Lácteos y huevos"),
    ("QUESO COLANTA*500g CUAJADA", "Lácteos y huevos"),
    ("SEDA DENT FCARDENT*35mt LL60mt LIMPIE", "Cuidado personal"),
    ("T.H NOSOTRAS*24und EXTRA PROTEC TELA", "Cuidado personal"),
    ("YOGURT VITAD*150g FRESA", "Lácteos y huevos"),
    ("YOGURT VITAD*150g MELOCOTON", "Lácteos y huevos"),
    ("YOGURT VITAD*150g MORA", "Lácteos y huevos"),
    # Estas dos salían en Despensa porque, al no existir Lácteos, ganaba otra palabra
    ("YOGURT ALPINA*106ml CEREAL C/SOBRECOP", "Lácteos y huevos"),
    ("MARGARINA CAMPI*250g C/SAL", "Lácteos y huevos"),
    # Una arepa con queso es una arepa, no un lácteo
    ("AREPAS MAIZAL*80g*10und QUESO", "Panadería"),
    ("JAMON PIETRAN*230g STANDAR", "Carnes"),
    # Cracker de mantequilla: la frase completa gana a `MANTEQUILLA`
    ("TOSTAOS BIMBO*15g*20und MANTEQUILLA", "Despensa"),
    # La avena de hojuelas es despensa; la líquida, lácteos
    ("AVENA QUAKER*400g HOJUELAS SIN GLUTEN", "Despensa"),
    ("AVENA LIQUIDA ALPINA*1000ml", "Lácteos y huevos"),
    ("BONYURT*200g FRESA", "Lácteos y huevos"),
)


def test_los_productos_reales_se_clasifican_bien():
    """Cada producto real de esa cuenta, en su etiqueta. Es la red que evita reincidir."""
    from app.defaults import ETIQUETAS_DICCIONARIO

    etiquetas = {
        sin_acentos_upper(n): n
        for nombres in ETIQUETAS_DICCIONARIO.values()
        for n in nombres
    }
    fallos = []
    for descripcion, esperada in PRODUCTOS_REALES:
        resultado = _por_diccionario(normalizar(descripcion), etiquetas)
        obtenida = resultado[0] if resultado else "SIN CLASIFICAR"
        if obtenida != esperada:
            fallos.append((descripcion, esperada, obtenida))
    assert fallos == [], f"{len(fallos)} de {len(PRODUCTOS_REALES)} mal: {fallos}"


def test_el_diccionario_solo_usa_etiquetas_que_la_app_siembra():
    """Toda etiqueta del diccionario tiene que estar en la siembra por defecto.

    Si alguien añade palabras para una etiqueta que la app no crea, esas palabras no
    clasifican **nada**: el diccionario empareja contra nombres de etiquetas existentes.
    """
    from app.defaults import ETIQUETAS_DICCIONARIO

    sembradas = {n for nombres in ETIQUETAS_DICCIONARIO.values() for n in nombres}
    faltan = [n for n in DICCIONARIO if n not in sembradas]
    assert faltan == [], f"el diccionario usa etiquetas que nadie crea: {faltan}"


def test_las_etiquetas_del_diccionario_se_completan_solas(client):
    """El caso de la cuenta real: le falta `Lácteos y huevos` y por eso no clasifica.

    Al leer las líneas, la app completa sola las etiquetas que el diccionario necesita.
    """
    from test_api import _pdf_minimo, _registrar

    _, h = _registrar(client)

    # Se borra `Lácteos y huevos`, que es lo que le pasaba a esa cuenta
    etiquetas = client.get("/etiquetas", headers=h).json()
    lacteos = next(e for e in etiquetas if e["nombre"] == "Lácteos y huevos")
    assert client.delete(f"/etiquetas/{lacteos['id']}", headers=h).status_code == 204
    assert not any(e["nombre"] == "Lácteos y huevos" for e in client.get("/etiquetas", headers=h).json())

    # Se sube una factura con productos de lácteos y se leen las líneas
    factura = client.post(
        "/facturas",
        headers=h,
        files={"archivo": ("f.pdf", _pdf_minimo("factura"), "application/pdf")},
    ).json()
    texto = "LECHE ALPINA*1000ml 30.900\nQUESO ALPINA*250g PARMESANO 32.700\nYOGURT VITAD*150g FRESA 3.350\n"
    r = client.post(f"/facturas/{factura['id']}/lineas", headers=h, json={"texto": texto})
    assert r.status_code == 200, r.text
    lineas = r.json()["lineas"]
    assert len(lineas) == 3

    # La etiqueta volvió a crearse sola…
    despues = client.get("/etiquetas", headers=h).json()
    lacteos = next((e for e in despues if e["nombre"] == "Lácteos y huevos"), None)
    assert lacteos is not None, "la etiqueta que el diccionario necesita se recrea sola"
    # …y las tres líneas quedaron clasificadas con ella
    assert [li["etiqueta_id"] for li in lineas] == [lacteos["id"]] * 3
    assert all(li["origen"] == "diccionario" for li in lineas)


def test_las_etiquetas_nuevas_clasifican_y_no_roban_productos():
    """Bebidas, panadería, snacks, congelados y mascotas: nuevas etiquetas con sus palabras.

    Lo importante aquí son las dos últimas: las palabras van **específicas** (`PAPA FRITA`)
    para que no se lleven por delante productos que son de otra etiqueta (`PAPAS A GRANEL`
    es mercado, no snack).
    """
    from app.defaults import ETIQUETAS_DICCIONARIO

    etiquetas = {
        sin_acentos_upper(n): n
        for nombres in ETIQUETAS_DICCIONARIO.values()
        for n in nombres
    }
    casos = (
        ("JUGO DE NARANJA HIT", "Bebidas"),
        ("GASEOSA COCA COLA 400ml", "Bebidas"),
        ("AGUA MINERAL 600ml", "Bebidas"),
        ("CERVEZA AGUILA LATA", "Bebidas"),
        ("PAN BIMBO*90g*4und DORADO HAMBURGUES", "Panadería"),
        ("BUÑUELO", "Panadería"),
        ("ALMOJABANA", "Panadería"),
        ("MECATO DETODITO", "Snacks"),
        ("PAPA FRITA MARGARITA", "Snacks"),
        ("HELADO CORONA", "Congelados"),
        ("NUGGETS CONGELADOS", "Congelados"),
        ("PURINA DOG CHOW 2kg", "Alimento"),
        ("CONCENTRADO PARA PERRO", "Alimento"),
        ("VETERINARIA CENTRAL", "Veterinario"),
        # Y los que NO se pueden robar
        ("PAPAS A GRANEL", "Frutas y verduras"),
        ("PAPA AMARILLA A GRANEL", "Frutas y verduras"),
        ("NARANJA DULCE A GRANEL", "Frutas y verduras"),
    )
    fallos = []
    for descripcion, esperada in casos:
        resultado = _por_diccionario(normalizar(descripcion), etiquetas)
        obtenida = resultado[0] if resultado else "SIN CLASIFICAR"
        if obtenida != esperada:
            fallos.append((descripcion, esperada, obtenida))
    assert fallos == [], f"{len(fallos)} de {len(casos)} mal: {fallos}"


def test_un_producto_que_no_es_bebida_no_cae_en_bebidas():
    """`AROMATICA` sola se llevaba la «VELA AROMATICA» a Bebidas: por eso no está.

    Es el tipo de choque que aparece solo al probar con productos reales: la palabra
    tiene dos sentidos y el diccionario se queda con el que no debe.
    """
    from app.defaults import ETIQUETAS_DICCIONARIO

    etiquetas = {
        sin_acentos_upper(n): n
        for nombres in ETIQUETAS_DICCIONARIO.values()
        for n in nombres
    }
    for descripcion in ("VELA AROMATICA VAINILLA", "PILAS AA DURACEL 4 UN"):
        resultado = _por_diccionario(normalizar(descripcion), etiquetas)
        obtenida = resultado[0] if resultado else "SIN CLASIFICAR"
        assert obtenida != "Bebidas", f"{descripcion} no es una bebida (dio {obtenida})"


def test_el_cafe_de_marca_no_se_confunde_con_la_cerveza():
    """`AGUILA ROJA` (café) contra `AGUILA` (cerveza): la frase completa manda.

    Este choque se vio en datos reales: el café se fue a Bebidas por la marca de la cerveza.
    """
    from app.defaults import ETIQUETAS_DICCIONARIO

    etiquetas = {
        sin_acentos_upper(n): n
        for nombres in ETIQUETAS_DICCIONARIO.values()
        for n in nombres
    }
    cafe = _por_diccionario(normalizar("CAFE AGUILA ROJA*380g MOLIDO"), etiquetas)
    assert cafe and cafe[0] == "Despensa", cafe
    cerveza = _por_diccionario(normalizar("CERVEZA AGUILA LATA 330ml"), etiquetas)
    assert cerveza and cerveza[0] == "Bebidas", cerveza


def test_las_etiquetas_de_transporte_y_la_salsa_fruco():
    """Parqueadero y Peajes (Transporte), y `SALSA FRUCO ... CARNES` es salsa, no carne.

    La salsa se colaba en Carnes porque la palabra CARNES es más larga que SALSA y gana;
    con la marca completa (`SALSA FRUCO`) vuelve a Despensa. Lo encontró la auditoría de
    los 120 productos reales de la factura.
    """
    from app.defaults import ETIQUETAS_DICCIONARIO

    etiquetas = {
        sin_acentos_upper(n): n
        for nombres in ETIQUETAS_DICCIONARIO.values()
        for n in nombres
    }
    casos = (
        ("SALSA FRUCO*165ml CARNES", "Despensa"),
        ("SALSA FRUCO*165ml SOYA", "Despensa"),
        ("PARQUEADERO CENTRO", "Parqueadero"),
        ("PARKING MIDAS", "Parqueadero"),
        ("PEAJE SALIDA BOGOTA", "Peajes"),
        ("TELEPEAJE", "Peajes"),
    )
    fallos = []
    for descripcion, esperada in casos:
        resultado = _por_diccionario(normalizar(descripcion), etiquetas)
        obtenida = resultado[0] if resultado else "SIN CLASIFICAR"
        if obtenida != esperada:
            fallos.append((descripcion, esperada, obtenida))
    assert fallos == [], fallos


def test_las_etiquetas_de_transporte_que_estaban_sin_palabras():
    """«Transporte público» y «Uber / DiDi» existían en la cuenta pero sin palabras."""
    from app.defaults import ETIQUETAS_DICCIONARIO

    etiquetas = {
        sin_acentos_upper(n): n
        for nombres in ETIQUETAS_DICCIONARIO.values()
        for n in nombres
    }
    casos = (
        ("PASAJE TRANSMILENIO", "Transporte público"),
        ("RECARGA SITP", "Transporte público"),
        ("UBER TRIP 29 SEP", "Uber / DiDi"),
        ("DIDI RIDE", "Uber / DiDi"),
        ("CABIFY VIAJE", "Uber / DiDi"),
        ("TAXI RADIOTAXI", "Uber / DiDi"),
    )
    fallos = []
    for descripcion, esperada in casos:
        resultado = _por_diccionario(normalizar(descripcion), etiquetas)
        obtenida = resultado[0] if resultado else "SIN CLASIFICAR"
        if obtenida != esperada:
            fallos.append((descripcion, esperada, obtenida))
    assert fallos == [], fallos
