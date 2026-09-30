"""Comprobantes de pago de un servicio (EMCALI por PSE): el monto es el «Valor del Pago».

Son PDF **digitales de dos columnas**. Antes se leían sin respetar las columnas y del número
de comprobante `TR260930020535rBgAnc` salía 260.930.020.535, del NIT `890399003-4` salía
890.399.003 y el documento se tomaba por «mercado» con artículos inventados. El pago real era
844.041.
"""

from __future__ import annotations

from decimal import Decimal

from test_api import _pdf_minimo

# Etiqueta y valor **en el mismo renglón** (el caso fácil)
CONFIRMACION = """EMCALI EICE ESP
Nit                                                              890399003-4
Referencia Pago                                                  125200
Consecutivo Comercio                                             450750619
Descripcion                                                      Factura Servicios Publicos
Fecha                                                            30 de septiembre de 2026 2:04:05 AM (GMT-5)
Valor Pago                                                       $ 844,041.00 COP
Banco                                                            BANCOLOMBIA
Codigo Transaccion                                               695413035
Estado                                                           APROBADA
Direccion IP                                                     186.168.139.47
"""

# Etiqueta de cabecera y valor **en el renglón de abajo**, en su columna
COMPROBANTE = """Comprobante en linea                    30 Sep 2026 02:05
Pago PSE
       Pago exitoso
       CUS 695413035
Comercio                     Referencia 1
CONSORCIO EMCALI             186.168.139.47
Fecha                        Referencia 2
30 Sep 2026 02:05            CC
Numero de factura            Referencia 3
125200                       16866684
Descripcion del pago         Valor del Pago
Factura Servicios Publicos   $844.041
Numero de comprobante        Costo de la transaccion
TR260930020535rBgAnc         $ 0
Producto origen
Cuenta de ahorros
 **** 0571
"""


def test_el_monto_sale_del_valor_del_pago():
    from app.facturas import detectar_monto

    assert detectar_monto(COMPROBANTE) == Decimal("844041")


def test_el_nit_no_es_el_monto():
    """`890399003-4` es un NIT, no un pago de 890 millones."""
    from app.facturas import detectar_monto

    assert detectar_monto(CONFIRMACION) == Decimal("844041.00")


def test_el_consecutivo_no_es_el_monto():
    """`TR260930020535...` no son 260.930 millones."""
    from app.facturas import detectar_monto

    assert detectar_monto(COMPROBANTE) < Decimal("10000000")


def test_es_un_servicio_y_no_un_mercado():
    from app.lineas import detectar_tipo, parsear_lineas

    articulos = parsear_lineas(COMPROBANTE)
    assert detectar_tipo(COMPROBANTE, articulos) == "servicios"
    assert detectar_tipo(CONFIRMACION, parsear_lineas(CONFIRMACION)) == "servicios"


def test_la_cuenta_enmascarada_no_es_un_articulo():
    """`**** 0571` es una cuenta, no un producto de 571 pesos."""
    from app.lineas import parsear_lineas

    for articulo in parsear_lineas(COMPROBANTE):
        assert articulo["valor_total"] != Decimal("571")


def test_la_extraccion_de_pdf_respeta_las_columnas(monkeypatch):
    """El modo `layout` es lo que mantiene la etiqueta junto a su valor."""
    from pypdf import PageObject

    original = PageObject.extract_text
    modos: list = []

    def espia(self, *args, **kwargs):
        modos.append(kwargs.get("extraction_mode"))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(PageObject, "extract_text", espia)
    from app.facturas import extraer_texto

    extraer_texto(_pdf_minimo("TOTAL 1.000"), "f.pdf", "application/pdf")
    assert "layout" in modos, "la extracción del PDF tiene que usar el modo layout"


# Confirmación de pago de un servicio (Gases de Occidente, una **imagen**): es lo que devuelve
# el OCR con `--psm 4`, que mantiene cada etiqueta junto a su valor. Con el modo automático
# Tesseract leía las dos columnas por separado y no se sabía qué valor iba con qué etiqueta.
CONFIRMACION_GAS = """O)
¡Pago realizado con éxito!
Hola Jose, tu pago fue exitoso. Te enviamos un correo con los detalles.
Detalles del pago:
Nite 800167643-5
Razón social: Gases de Occidente S.A. ESP
Estado Transacció Aprobado
Referencia de pago: 5753155975914591
Transacción/CUS: 695417658
Tipo de usuario: Persona
Concepto: Pago de factura
Número de referencia: 393730364
Monto: $46.477
Fecha: 30/09/2026 02:27:31
"""


def test_la_confirmacion_de_pago_no_toma_un_numero_de_documento():
    """El NIT, la referencia y el CUS son documentos; el pago son 46.477."""
    from app.facturas import detectar_monto

    assert detectar_monto(CONFIRMACION_GAS) == Decimal("46477")


def test_la_confirmacion_de_pago_es_un_servicio():
    from app.lineas import detectar_tipo, parsear_lineas

    assert detectar_tipo(CONFIRMACION_GAS, parsear_lineas(CONFIRMACION_GAS)) == "servicios"


def test_el_ocr_lee_una_sola_columna(monkeypatch):
    """`--psm 4`: sin esto, Tesseract separa las dos columnas y pierde el emparejamiento."""
    import pytesseract

    configuraciones: list = []

    def espia(imagen, *args, **kwargs):
        # No se ejecuta Tesseract: en CI no está instalado y aquí solo se comprueba **con qué
        # configuración se llama** (que es lo que decide si lee una columna o dos).
        configuraciones.append(kwargs.get("config"))
        return ""

    monkeypatch.setattr(pytesseract, "image_to_string", espia)
    from PIL import Image

    from app.facturas import _ocr_imagen

    _ocr_imagen(Image.new("RGB", (60, 20), "white"))
    assert "--psm 4" in configuraciones, "el OCR tiene que leer una sola columna"
