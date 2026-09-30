"""La ayuda de Konta: cómo se hace cada cosa, paso a paso, con la pantalla por su nombre.

El manual es la fuente de verdad de la ayuda. Se busca **por significado** con embeddings locales
(«no me cuadra la plata» encuentra «saber por qué mi saldo cambió»), y si el Ollama no está se
cae a la búsqueda por palabras: nunca se queda sin responder.

Los pasos nombran la pantalla tal como aparece en el menú, porque quien pregunta está mirando la
app.
"""

from __future__ import annotations

from . import embeddings
from .config import get_settings

# tema → pasos. El tema es lo que se enseña como título.
TEMAS: dict[str, list[str]] = {
    "registrar un gasto o un ingreso": [
        "Entra en Movimientos → Transacciones y pulsa «Nuevo movimiento».",
        "Elige el tipo (gasto o ingreso), el monto y la fecha.",
        "Escribe una descripción que después te sirva para buscarlo.",
        "Si quieres, asígnale categoría, etiqueta y cuenta.",
        "Guarda: el saldo y los reportes se actualizan solos.",
    ],
    "subir una factura o un recibo": [
        "Entra en Herramientas → Facturas y elige el archivo (PDF o foto): se lee al instante.",
        "Si trae artículos, pulsa «Leer líneas» para partirla en productos.",
        "Revisa el panel «Revisa antes de registrar»: monto, fecha y artículos.",
        "Registra la compra (un solo gasto con el detalle) o confirma las líneas una por una.",
    ],
    "leer una factura con IA": [
        "Sube la factura normalmente: el lector de Konta la lee gratis.",
        "Si la lectura queda dudosa (sin monto, o un mercado sin artículos), en esa misma factura "
        "aparece «🤖 Leer con IA» en ámbar.",
        "Púlsalo: cuesta una lectura de tu plan y reemplaza la lectura de esa factura (no crea "
        "otra y no toca lo que ya registraste).",
        "Si te quedas sin lecturas, en «Ver planes» puedes comprar un paquete o subir de plan.",
    ],
    "saber por qué mi saldo cambió": [
        "Entra en Movimientos → Cuentas y mira el saldo de cada cuenta.",
        "Abre Movimientos → Transacciones y filtra por esa cuenta y el mes que te interesa.",
        "Ojo: el saldo solo cuenta lo que ya pasó; una transacción con fecha futura no entra hasta "
        "ese día.",
        "Si el saldo de tu banco no coincide con el saldo inicial de la cuenta, corrígelo en la "
        "cuenta.",
    ],
    "separar los gastos de casa y apartamento": [
        "Entra en Organización → Categorías y crea una por lugar: «Casa» y «Apartamento».",
        "En Organización → Etiquetas, crea las del servicio: Acueducto, Energía, Gas, Internet.",
        "Al registrar el gasto, elige la categoría del lugar y la etiqueta del servicio.",
        "En Análisis → Reportes verás el total por categoría y podrás comparar los dos lugares.",
    ],
    "hacer un presupuesto": [
        "Entra en Análisis → Presupuestos y pulsa «Nuevo».",
        "Elige si el límite es por categoría o por etiqueta (por ejemplo, Mercado o Restaurantes).",
        "Pon el monto del mes.",
        "La app te avisa cuando te acercas y cuando te pasas.",
    ],
    "entender el gasto fijo del mes": [
        "Konta suma tus gastos recurrentes y tus seguros activos, y reparte las anuales por mes.",
        "Lo ves en Resumen, en la tarjeta «Gasto fijo / mes».",
        "Los cobros que están por venir aparecen en «Próximos pagos».",
    ],
    "agregar un gasto que se repite": [
        "Entra en Recurrentes → Gastos recurrentes y pulsa «Nuevo».",
        "Pon el nombre (Arriendo, Colegio, Netflix), el monto y cada cuánto se cobra.",
        "Elige el día de cobro y la cuenta o tarjeta.",
        "Konta registra el gasto solo cuando llega la fecha.",
    ],
    "registrar un ingreso que se repite": [
        "Entra en Recurrentes → Ingresos recurrentes.",
        "Pon el nombre (Nómina), el monto y la frecuencia.",
        "Indica el día en que lo recibes.",
        "Aparecerá en Resumen dentro de lo que viene este mes.",
    ],
    "mirar mis tarjetas y lo que debo": [
        "Entra en Movimientos → Tarjetas.",
        "Cada tarjeta muestra su cupo y la deuda por movimientos.",
        "Las compras con tarjeta de crédito no bajan tu saldo hasta que pagas la tarjeta.",
        "Cuando pagues, registra la transferencia a la tarjeta para que el saldo cuadre.",
    ],
    "registrar la deuda y las cuotas de un extracto": [
        "Entra en Herramientas → Extractos y sube el extracto de la tarjeta.",
        "Revisa las compras que detectó y corrige lo que haga falta.",
        "Pásalas a transacciones y marca las que son a cuotas.",
        "En Herramientas → Deuda y cuotas ves el total por pagar y cuánto te toca cada mes.",
    ],
    "poner una meta de ahorro": [
        "Entra en Análisis → Metas y pulsa «Nueva».",
        "Pon cuánto quieres ahorrar y para cuándo.",
        "Ve abonando cuando apartes la plata.",
        "La meta te muestra cuánto llevas y cuánto te falta por mes.",
    ],
    "ver cómo voy este mes": [
        "Entra en Resumen.",
        "Ahí están los ingresos, los gastos, el balance, el gasto fijo y lo que viene.",
        "Puedes cambiar de mes con el selector de arriba.",
    ],
    "ver en qué se me va la plata": [
        "Entra en Análisis → Reportes.",
        "Mira el gasto por categoría del mes y compáralo con el anterior.",
        "En las facturas con artículos, baja al detalle por etiqueta y por producto.",
    ],
    "saber si me alcanza para lo que viene": [
        "Entra en Análisis → Flujo de caja.",
        "Verás lo que entra y lo que sale en los próximos meses.",
        "Las líneas que se repiten (arriendo, colegio) ya están incluidas.",
    ],
    "controlar los seguros y sus vencimientos": [
        "Entra en Movimientos → Seguros.",
        "Registra cada póliza con su valor y su fecha de vencimiento.",
        "Konta te avisa antes de que se venza.",
    ],
    "organizar con categorías y etiquetas": [
        "La categoría es el lugar o el grupo grande (Casa, Mercado, Transporte).",
        "La etiqueta es el detalle (Acueducto, Restaurantes, Gasolina).",
        "Se crean en Organización → Categorías y Organización → Etiquetas.",
        "Dentro de una categoría puedes tener subetiquetas para afinar más.",
    ],
    "usar la lista del mercado y los productos": [
        "Entra en Herramientas → Mercado.",
        "Ahí ves los productos que has comprado, con su precio y cuántas veces.",
        "Puedes armar la lista del mercado y comparar precios entre compras.",
    ],
    "importar movimientos de un extracto": [
        "Entra en Herramientas → Importar.",
        "Sube el archivo del banco (o pega el texto).",
        "Revisa la vista previa: la app propone categoría y etiqueta por reglas anteriores.",
        "Confirma para crear los movimientos.",
    ],
    "arreglar una lectura que salió mal": [
        "Entra en Herramientas → Facturas y abre la factura.",
        "Corrige el monto o la fecha con «✏️ Corregir».",
        "Si un renglón quedó mal, edítalo o bórralo; si falta uno, agrégalo.",
        "Konta aprende: si el mismo renglón se ignora dos veces, lo ignora solo la próxima vez.",
    ],
    "cambiar de plan o comprar lecturas": [
        "En Herramientas → Facturas, arriba, ves tu cupo del mes y el botón «Ver planes».",
        "Ahí compara qué incluye cada plan y cuál tienes.",
        "Para comprar un paquete de lecturas o subir de plan, usa el botón de compra.",
        "El cobro en línea se está terminando de conectar; mientras tanto, escríbenos.",
    ],
    "exportar o respaldar mis datos": [
        "Entra en Configuración → Respaldo.",
        "Descarga tus datos para guardarlos o pasarlos a otro lado.",
        "Los archivos de las facturas se borran solos a los pocos días: si necesitas el documento, "
        "guárdalo tú.",
    ],
    "cambiar la moneda o ver la tasa del dólar": [
        "Entra en Configuración → Monedas.",
        "Ahí están las monedas y la TRM del día.",
        "Konta usa la TRM para convertir cuando tienes movimientos en dólares.",
    ],
    "configurar los avisos": [
        "Entra en Configuración → Notificaciones.",
        "Elige qué quieres que te avise: vencimientos, cobros, presupuestos.",
    ],
    "preguntarle al asistente": [
        "Entra en Herramientas → Asistente.",
        "Escribe tu pregunta o pulsa una de las sugerencias.",
        "El asistente consulta tus datos reales y te dice qué miró.",
        "Cada pregunta es independiente y cuenta en tu plan.",
    ],
}


def temas() -> list[str]:
    return list(TEMAS)


def _embedder():
    """El embedder local, con más margen de espera que el del clasificador."""
    if not get_settings().ollama_url:
        return None
    return embeddings.make_embedding(timeout=get_settings().ayuda_ollama_timeout)


def _vector_de_temas() -> list[tuple[str, list[float]]]:
    """Los vectores de los temas, calculados una vez y guardados en memoria."""
    global _CACHE
    if _CACHE is None:
        embed = _embedder()
        calculados = []
        if embed is not None:
            for tema, pasos in TEMAS.items():
                vector = embed(f"{tema}. {' '.join(pasos)}")
                if vector:
                    calculados.append((tema, vector))
        _CACHE = calculados
    return _CACHE


_CACHE: list[tuple[str, list[float]]] | None = None


def precalentar() -> None:
    """Calcula el índice del manual en segundo plano (tarda: son 25 temas con el modelo local).

    Se llama al arrancar para que la primera pregunta no se encuentre el índice frío. Si falla, no
    pasa nada: la ayuda sigue funcionando por palabras.
    """
    import threading

    def trabajo() -> None:
        try:
            _vector_de_temas()
        except Exception:  # noqa: BLE001 — el índice es una mejora, no un requisito
            pass

    threading.Thread(target=trabajo, name="indice-ayuda", daemon=True).start()


def _por_palabras(consulta: str, limite: int) -> list[dict]:
    """El plan B: buscar por palabras, como antes de los embeddings."""
    buscado = consulta.lower().strip()
    palabras = [p for p in buscado.split() if len(p) > 3]
    encontrados = []
    for tema, pasos in TEMAS.items():
        texto = f"{tema} {' '.join(pasos)}".lower()
        puntos = sum(1 for palabra in palabras if palabra in texto)
        if buscado in tema.lower():
            puntos += 3
        if puntos:
            encontrados.append((puntos, tema, pasos))
    encontrados.sort(key=lambda x: -x[0])
    return [
        {"tema": tema, "pasos": pasos, "como": "palabras", "puntos": puntos}
        for puntos, tema, pasos in encontrados[:limite]
    ]


def buscar(consulta: str | None, limite: int = 3) -> dict:
    """Los temas que mejor responden a lo que se pregunta.

    Devuelve `resultados` (con su similitud, para que el asistente sepa si son de fiar) y el
    `minimo` exigido. Si ningún tema se parece lo suficiente, `resultados` va vacío y el asistente
    dice que no lo tiene — que es mejor que inventarse los pasos.
    """
    consulta = (consulta or "").strip()
    if not consulta:
        return {"temas": temas(), "resultados": [], "minimo": 0.0, "como": "sin consulta"}

    minimo = get_settings().ayuda_similitud_minima
    embed = _embedder()
    vector = embed(consulta, "consulta") if embed else None
    indices = _vector_de_temas() if vector else []
    if vector and indices:
        puntos = [
            {"tema": tema, "pasos": TEMAS[tema], "como": "significado",
             "similitud": round(embeddings.parecido(vector, v), 4)}
            for tema, v in indices
        ]
        puntos.sort(key=lambda x: -x["similitud"])
        buenos = [p for p in puntos[:limite] if p["similitud"] >= minimo]
        if buenos:
            return {"resultados": buenos, "minimo": minimo, "como": "significado"}
        return {
            "temas": temas(),
            "resultados": [],
            "minimo": minimo,
            "como": "significado",
            "nota": "Ningún tema del manual se parece lo suficiente: dile al usuario que no lo tienes.",
        }

    # Sin embeddings (Ollama caído o apagado), se busca por palabras
    resultados = _por_palabras(consulta, limite)
    return {
        "resultados": resultados,
        "minimo": 0.0,
        "como": "palabras",
        **({} if resultados else {"temas": temas(), "nota": "No encontré ese tema por palabras."}),
    }
