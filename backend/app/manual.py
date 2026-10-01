"""La ayuda de Konta: cómo se hace cada cosa, paso a paso, con la pantalla por su nombre.

El manual es la fuente de verdad de la ayuda. Se busca **por significado** con embeddings locales
(«no me cuadra la plata» encuentra «saber por qué mi saldo cambió»), y si el Ollama no está se
cae a la búsqueda por palabras: nunca se queda sin responder.

Los pasos nombran la pantalla tal como aparece en el menú, porque quien pregunta está mirando la
app.
"""

from __future__ import annotations

import contextlib

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
    "transferir dinero entre mis cuentas": [
        "Entra en Movimientos → Transacciones y pulsa «Nuevo movimiento».",
        "En el tipo elige «Transferencia entre cuentas».",
        "Pon el monto y la fecha, y elige la cuenta de **origen** y la de **destino**.",
        "Una transferencia no lleva categoría ni etiqueta: no es un gasto, es mover plata tuya.",
        "Ojo con el saldo: la transferencia **baja** el saldo de la cuenta de origen y **sube** el de "
        "la de destino; el total de tu dinero no cambia.",
        "Para pagar una tarjeta de crédito se hace igual, pero en el destino eliges la **tarjeta**: "
        "eso registra el pago y baja la deuda.",
    ],
    "crear una cuenta y poner su saldo inicial": [
        "Entra en Movimientos → Cuentas y pulsa «Nueva».",
        "Pon el nombre (Bancolombia, Efectivo…), el tipo y el **saldo inicial**: la plata que hay "
        "hoy en esa cuenta.",
        "El saldo que ves después es ese saldo inicial más lo que ha entrado y menos lo que ha "
        "salido.",
        "Si el saldo del banco no coincide, corrige el **saldo inicial** en la misma pantalla: se "
        "ajusta sin tocar tus movimientos.",
    ],
    "corregir o borrar un movimiento": [
        "Entra en Movimientos → Transacciones y busca el movimiento.",
        "Pulsa «Editar» para cambiar el monto, la fecha, la descripción, la categoría o la cuenta.",
        "Pulsa «Eliminar» para borrarlo (y el saldo se recompone solo).",
        "Si el movimiento salió de una factura, es mejor corregirlo desde Facturas: así la factura y "
        "el movimiento siguen contando lo mismo.",
    ],
    "el IVA de mis facturas": [
        "Cuando subes una factura con IVA, Konta lo guarda aparte del total.",
        "En Análisis → Reportes ves el IVA del mes y su peso sobre tus compras.",
        "Sirve para saber cuánto de lo que gastaste fue impuesto.",
        "Si la factura no trae el IVA desglosado, no se inventa: queda sin ese dato.",
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


def _embedder(timeout: float | None = None):
    """El embedder local.

    Para **indexar** se le da margen (es trabajo de una vez, en segundo plano); para **preguntar**
    se le da poco: si el modelo está frío, Ollama puede tardar 30 s en cargarlo, y al usuario no se
    le hace esperar eso — se responde por palabras y ya.
    """
    if not get_settings().ollama_url:
        return None
    return embeddings.make_embedding(
        timeout=timeout if timeout is not None else get_settings().ayuda_ollama_timeout
    )


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
        # El índice es una mejora, no un requisito: si falla, la ayuda sigue por palabras
        with contextlib.suppress(Exception):
            _vector_de_temas()

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


def buscar(consulta: str | None, limite: int = 5) -> dict:
    """Los temas que podrían responder a lo que se pregunta, con su similitud.

    **Quien decide es el modelo, no el número**: con `nomic-embed-text` una pregunta que no está en
    el manual puntúa ~0,63 y una que sí está ~0,62, así que un umbral absoluto no separa nada
    (medido). Por eso se devuelven los 5 candidatos con su puntuación y el asistente juzga si
    alguno responde de verdad; si ninguno lo hace, tiene que decir que no lo tiene.
    """
    consulta = (consulta or "").strip()
    if not consulta:
        return {"temas": temas(), "resultados": [], "minimo": 0.0, "como": "sin consulta"}

    minimo = get_settings().ayuda_similitud_minima
    # Poco margen para preguntar: si el modelo está frío, se responde por palabras
    embed = _embedder(timeout=get_settings().ayuda_consulta_timeout)
    vector = embed(consulta, "consulta") if embed else None
    indices = _vector_de_temas() if vector else []
    if vector and indices:
        puntos = [
            {"tema": tema, "pasos": TEMAS[tema], "como": "significado",
             "similitud": round(embeddings.parecido(vector, v), 4)}
            for tema, v in indices
        ]
        puntos.sort(key=lambda x: -x["similitud"])
        candidatos = [p for p in puntos[:limite] if p["similitud"] >= minimo]
        if candidatos:
            return {
                "resultados": candidatos,
                "como": "significado",
                "aviso": (
                    "Estos son los temas del manual que más se parecen, pero la puntuación no "
                    "decide: si ninguno responde a lo que preguntan, di que no lo tienes."
                ),
            }
        return {
            "temas": temas(),
            "resultados": [],
            "como": "significado",
            "nota": "Ningún tema del manual se parece: dile al usuario que no lo tienes.",
        }

    # Sin embeddings (Ollama caído o apagado), se busca por palabras
    resultados = _por_palabras(consulta, limite)
    return {
        "resultados": resultados,
        "minimo": 0.0,
        "como": "palabras",
        **({} if resultados else {"temas": temas(), "nota": "No encontré ese tema por palabras."}),
    }
