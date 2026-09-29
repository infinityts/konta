"""Clasifica artículos de un recibo a etiquetas del árbol.

Tres niveles, de más barato a más listo:

1. **Historial** (`reglas_ocr`): lo que el usuario ya corrigió antes.
2. **Diccionario**: palabras clave típicas de un recibo colombiano.
3. **Embeddings**: similitud semántica contra las etiquetas, vía Ollama.
   Si Ollama no responde, simplemente se salta este nivel.

Lo que no se puede decidir queda como `sin_clasificar` para que el usuario lo
elija una vez (y la próxima ya lo sepa).

El diccionario empareja contra **nombres de etiquetas** del usuario, así que las
palabras de aquí solo sirven si existe la etiqueta correspondiente (las crea
`defaults.sembrar_etiquetas_diccionario`). Un test vigila esa coherencia.
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Etiqueta, ReglaOcr

# Palabras clave por **nombre de etiqueta**. Solo aplican si el usuario tiene
# esa etiqueta creada.
DICCIONARIO: dict[str, tuple[str, ...]] = {
    # El **orden importa**: gana la primera etiqueta que encuentra una palabra suya. Por eso
    # van primero las que describen el producto ya elaborado (una carne, un lácteo, un
    # aseo) y **al final** las frutas y verduras: `PEPINO RES` es carne de res, no un
    # pepino, y `SALSA DE TOMATE` es despensa, no un tomate.
    "Carnes": (
        "POLLO", "PECHUGA", "CARNE", "RES", "CERDO", "PESCADO", "CHORIZO", "JAMON",
        "MOLIDA", "COSTILLA", "LOMO", "TOCINO", "TOCINETA", "SALCHICHA", "MUSLO", "ALAS",
        "FILETE", "PERNIL", "CHULETA", "MORCILLA", "PUNTA DE ANCA", "SOBREBARRIGA",
        "MUCHACHO", "MENUDENCIA", "HUESO", "PIERNA", "PEZUNA", "HIGADO", "BOLA NEGRA",
        "PEPINO RES", "LENGUA", "RABO", "OSOBUCO",
    ),
    "Lácteos y huevos": (
        "LECHE", "QUESO", "HUEVO", "YOGUR", "YOGURT", "MANTEQUILLA", "MARGARINA", "CREMA",
        "KUMIS", "CUAJADA", "AREQUIPE", "PARMESANO", "MOZAREL", "CREMOSINO", "CAMPESINO",
        "ALQUERIA", "COLANTA", "ALPINA", "BONYURT", "VITAD", "PARMALAT", "YOPLAIT",
        "DOBLE CREMA", "QUESO PERA", "CRIOLLO", "CREMA DE LECHE",
        # La **avena líquida** es de nevera, así que va aquí. Las hojuelas de avena se
        # quedan en Despensa por la palabra `HOJUELAS`, que es más larga y gana.
        "AVENA",
    ),
    "Cuidado personal": (
        "SHAMPOO", "CREMA DENTAL", "SEDA DENT", "HILO DENTAL", "CEPILLO DE DIENTES",
        "CEPILLO", "CEP COLGATE", "DESODORANTE", "DESOD", "TOALLA HIGIENICA", "TOALLA",
        "T.H", "NOSOTRAS", "PANAL", "AFEITAR", "COLGATE", "PROTEX",
        "SEDAL", "JABON DE BANO", "ENJUAGUE", "REXONA", "PAPEL HIGIENICO",
    ),
    "Aseo del hogar": (
        "JABON", "DETERGENTE", "BLANQUEADOR", "LIMPIADOR", "SUAVIZANTE", "ESCOBA",
        "BOLSA", "CLORO", "LAVAPLATOS", "ESPONJA", "SERVILLETA", "FABULOSO", "DESMAN",
        "QUITAMANCHAS", "VANISH", "TC FAMILIA", "ACOLCHAMAX", "TOALLA DE COCINA",
        "PAPEL DE COCINA", "FAB", "AXION", "SUAVITEL", "BLANQUITA",
    ),
    # Bebidas, panadería, snacks y congelados: estaban todas mezcladas en Despensa.
    # Las palabras van **largas y específicas** a propósito (`PAPA FRITA`, no `PAPAS`),
    # porque gana la más larga: con `PAPAS` a secas, las papas del mercado caerían aquí.
    "Bebidas": (
        "JUGO DE", "JUGO", "GASEOSA", "COCA COLA", "COCACOLA", "POSTOBON", "PEPSI",
        "AGUA MINERAL", "AGUA", "REFRESCO", "MALTA", "PONY", "HIT", "CERVEZA",
        "AGUILA", "POKER", "CLUB COLOMBIA", "VINO", "GATORADE", "POWERADE",
        # `AROMATICA` a secas **no** va aquí: una «VELA AROMATICA» se iría a bebidas. El
        # té se cubre con `TE ` y `TE VERDE`, que no chocan con nada.
        "ENERGIZANTE", "TE ", "TE VERDE", "TE HINDU", "INFUSION", "SODA",
    ),
    "Panadería": (
        "PAN ", "PANADERIA", "BOLLO", "BUÑUELO", "BUNUELO", "ALMOJABANA", "PANDEBONO",
        "CROISSANT", "PONQUE", "TORTA", "BROWNIE", "BAGUETTE", "AREPAS", "AREPA DE",
    ),
    "Snacks": (
        "MECATO", "DETODITO", "MARGARITA", "CHITOS", "PLATANITOS", "CHOCOLATINA",
        "CHICLE", "MANI", "PAPA FRITA", "PAPAS FRITAS", "SNACK", "JET", "TOSTADITAS",
    ),
    "Congelados": (
        "CONGELADO", "NUGGETS", "HELADO", "PIZZA CONGELADA", "HAMBURGUESA CONGELADA",
    ),
    "Despensa": (
        # `AGUILA ROJA` es un café, y `AGUILA` a secas es una cerveza (Bebidas): sin la
        # frase completa, el café se iba a bebidas.
        "AGUILA ROJA",
        "ARROZ", "ACEITE", "PANELA", "PASTA", "AZUCAR", "CAFE", "HARINA", "ATUN",
        "SARDINA", "GALLETA", "CHOCOLATE", "SALSA", "CONDIMENTO", "FRIJOL",
        "LENTEJA", "MAIZ", "CEREAL", "ESPAGUETI", "VINAGRE", "MAYONESA",
        "MIEL", "GELATINA", "PANTAJADO", "SAL ", "SALSA DE TOMATE", "HOJUELAS",
        # `SALSA FRUCO*165ml CARNES` es una **salsa** para carnes: sin la marca, la
        # palabra CARNES (más larga que SALSA) se la llevaba a la etiqueta Carnes.
        "SALSA FRUCO",
        # `TOSTAOS BIMBO` es una galleta: sin la frase completa, `MANTEQUILLA` (más corta
        # pero de Lácteos) se la llevaría a lácteos.
        "TOSTAOS BIMBO",
        "SALSA NAPOLITANA", "SOPA", "CALDO", "LEVADURA", "AREPA", "TOSTADA",
        "TORTILLA", "SAZONADOR", "OREGANO", "TOMILLO", "COLOR MAC", "ACEITUNA",
        # «de tomate» y «en polvo» son más largas que TOMATE y CEBOLLA, así que ganan:
        # una salsa de tomate es despensa y una cebolla en polvo también
        "DE TOMATE", "EN POLVO", "TOSTADITA",
        "SARDINAS", "SALCHICHON", "CEREALES", "GALLETAS",
    ),
    "Frutas y verduras": (
        "TOMATE", "CEBOLLA", "PAPA", "PLATANO", "MANZANA", "NARANJA", "LECHUGA",
        "ZANAHORIA", "LIMON", "AGUACATE", "BANANO", "FRUTA", "VERDURA", "CHONTO",
        "GUINEO", "MARACUYA", "MANGO", "PINA", "PEPINO", "AHUYAMA", "ESPINACA",
        "BROCOLI", "ZAPALLO", "YUCA", "ARVEJA", "HABICHUELA", "CILANTRO", "PEREJIL",
        "UVA", "SANDIA", "GRANADILLA", "APIO", "COLIFLOR", "PIMENTON", "AJO",
        "ENSALADA", "REMOLACHA", "RABANO", "ACELGA", "REPOLLO", "MAZORCA",
        "CHAMPINON", "MANDARINA", "PAPAYA", "GUAYABA", "LULO", "CURUBA", "MELON",
        "PERA", "GRANADA", "TOMATE DE ARBOL", "KIWI", "REPOLLITA", "PINA ORO",
    ),
    # Mascotas: la categoría y sus etiquetas ya existen, pero sin palabras el diccionario
    # no podía clasificar ni un concentrado.
    "Alimento": (
        "PURINA", "DOGOURMET", "PEDIGREE", "WHISKAS", "PRO PLAN", "DOG CHOW",
        "CAT CHOW", "CONCENTRADO PARA", "ALIMENTO PARA", "ARENA PARA GATO",
    ),
    "Veterinario": ("VETERINARIA", "VETERINARIO"),
    "Parqueadero": ("PARKING", "PARQUEADERO", "PARQUEADEROS", "ESTACIONAMIENTO"),
    "Peajes": ("PEAJE", "PEAJES", "TELEPEAJE"),
    "Gasolina": (
        "GASOLINA", "COMBUSTIBLE", "DIESEL", "TERPEL", "PRIMAX", "TEXACO",
        "GALONES", "BIODIESEL", "EDS",
    ),
    # Compras que no son de mercado. Sin esto, una compra de ropa salía entera
    # «sin clasificar» y había que corregir artículo por artículo.
    "Ropa": (
        "CAMISETA", "CAMISA", "PANTALON", "JEANS", "BLUSA", "VESTIDO", "ROPA",
        "CHAQUETA", "SUDADERA", "FALDA", "INTERIOR", "PIJAMA", "MEDIAS",
        "CALCETINES", "GORRA", "CINTURON", "CORBATA", "BUZO", "SHORT",
    ),
    "Calzado": (
        "ZAPATO", "ZAPATILLA", "TENIS", "BOTA", "SANDALIA", "TACONES",
        "CHANCLETA", "ALPARGATA", "MOCASIN",
    ),
    "Tecnología": (
        "CELULAR", "TELEFONO", "COMPUTADOR", "PORTATIL", "TABLET", "AUDIFONOS",
        "CARGADOR", "MONITOR", "TECLADO", "MOUSE", "IMPRESORA", "USB",
        "DISCO DURO", "MEMORIA SD", "CABLE HDMI", "PARLANTE", "ROUTER",
    ),
}

UMBRAL_EMBEDDINGS = 0.62


def normalizar(descripcion: str) -> str:
    """Mayúsculas, sin acentos, sin códigos ni medidas: 'PECHUGA POLLO 1.2KG' -> 'PECHUGA POLLO'."""
    t = "".join(
        c for c in unicodedata.normalize("NFD", descripcion) if unicodedata.category(c) != "Mn"
    ).upper()
    t = re.sub(r"[^A-Z0-9 ]+", " ", t)
    t = re.sub(r"\b\d+[A-Z]*\b", " ", t)  # códigos y medidas (500G, 1100ML, 1)
    return re.sub(r"\s+", " ", t).strip()


def _por_historial(
    session: Session, usuario_id, patron: str
) -> tuple[object, str, Decimal] | None:
    reglas = session.scalars(
        select(ReglaOcr).where(ReglaOcr.usuario_id == usuario_id)
    ).all()
    if not reglas:
        return None

    for r in reglas:  # coincidencia exacta
        if r.patron == patron:
            return r.etiqueta_id, "historial", Decimal("0.99")

    # Coincidencia parcial: se queda la regla más específica (patrón más largo)
    candidatas = [r for r in reglas if r.patron and (r.patron in patron or patron in r.patron)]
    if candidatas:
        mejor = max(candidatas, key=lambda r: len(r.patron))
        return mejor.etiqueta_id, "historial", Decimal("0.90")
    return None


def _por_diccionario(patron: str, por_nombre: dict[str, object]) -> tuple[object, str, Decimal] | None:
    """Gana la palabra clave **más larga**: 'CREMA DENTAL' supera a 'CREMA'."""
    mejor: tuple[int, object] | None = None
    for nombre, claves in DICCIONARIO.items():
        etiqueta_id = por_nombre.get(sin_acentos_upper(nombre))
        if etiqueta_id is None:
            continue
        for clave in claves:
            k = sin_acentos_upper(clave.strip())
            if not k:
                continue
            # (?:S|ES)? tolera plurales: HUEVO -> HUEVOS
            if re.search(rf"\b{re.escape(k)}(?:S|ES)?\b", patron) and (
                mejor is None or len(k) > mejor[0]
            ):
                mejor = (len(k), etiqueta_id)
    if mejor is not None:
        return mejor[1], "diccionario", Decimal("0.85")
    return None


def sin_acentos_upper(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    ).upper()


def _por_embeddings(
    patron: str, por_nombre: dict[str, object], emb
) -> tuple[object, str, Decimal] | None:
    if emb is None:
        return None
    vector = emb(patron)
    if vector is None:
        return None

    import math

    mejor_id, mejor_sim = None, 0.0
    for nombre, etiqueta_id in por_nombre.items():
        claves = DICCIONARIO.get(nombre, ())
        perfil = f"{nombre}. " + ", ".join(claves) if claves else nombre
        pv = emb(perfil)
        if pv is None or len(pv) != len(vector):
            continue
        # Ya se comprobó arriba que miden lo mismo
        prod = sum(a * b for a, b in zip(vector, pv, strict=True))
        na = math.sqrt(sum(a * a for a in vector))
        nb = math.sqrt(sum(b * b for b in pv))
        sim = prod / (na * nb) if na and nb else 0.0
        if sim > mejor_sim:
            mejor_id, mejor_sim = etiqueta_id, sim

    if mejor_id is not None and mejor_sim >= UMBRAL_EMBEDDINGS:
        return mejor_id, "embeddings", Decimal(str(round(mejor_sim, 3)))
    return None


def clasificar(
    session: Session,
    usuario_id,
    descripcion: str,
    etiquetas: list[Etiqueta],
    emb=None,
) -> tuple[object | None, str, Decimal | None]:
    """Devuelve (etiqueta_id, origen, confianza)."""
    patron = normalizar(descripcion)
    if not patron:
        return None, "sin_clasificar", None

    por_nombre = {sin_acentos_upper(e.nombre): e.id for e in etiquetas}

    for nivel in (
        lambda: _por_historial(session, usuario_id, patron),
        lambda: _por_diccionario(patron, por_nombre),
        lambda: _por_embeddings(patron, por_nombre, emb),
    ):
        try:
            resultado = nivel()
        except Exception:  # noqa: BLE001 — los embeddings son opcionales: si Ollama no responde se sigue con el siguiente nivel
            resultado = None
        if resultado:
            return resultado

    return None, "sin_clasificar", None
