"""Esquemas Pydantic (entradas/salidas de la API)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import (
    EstadoSuscripcion,
    Periodicidad,
    PeriodicidadIngreso,
    TipoCategoria,
    TipoTarjeta,
    TipoTransaccion,
)
from .recurrencia import hoy

# --- auth ---


class UserCreate(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8)
    moneda_principal: str = "COP"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    nombre: str
    moneda_principal: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- categorias ---


class CategoriaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: TipoCategoria
    icono: str | None = None
    color: str | None = None


class CategoriaUpdate(BaseModel):
    nombre: str | None = None
    tipo: TipoCategoria | None = None
    icono: str | None = None
    color: str | None = None


class CategoriaOut(CategoriaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class CopiarEtiquetasIn(BaseModel):
    """Copiar las etiquetas de **otra** categoría a esta (Casa 2 con lo de Casa 1).

    `previsualizar` calcula el plan y **no guarda nada**, para poder enseñarlo antes
    de tocar el árbol del usuario.
    """

    origen_id: uuid.UUID
    previsualizar: bool = False


class CopiarEtiquetasOut(BaseModel):
    previsualizar: bool = False
    # Las que se crearon (vacío si era una previsualización)
    creadas: list[EtiquetaOut] = []
    # Rutas que ya existían en el destino: no se duplican
    omitidas: list[str] = []
    # Rutas que se crearían: solo en la previsualización
    plan: list[str] = []
    total_creadas: int = 0


# --- tarjetas ---


class TarjetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    banco: str | None = None
    tipo: TipoTarjeta
    moneda: str = "COP"
    dia_corte: int | None = Field(None, ge=1, le=31)
    dia_pago: int | None = Field(None, ge=1, le=31)
    limite: Decimal | None = Field(None, ge=0)
    tasa_interes: Decimal | None = Field(None, ge=0)
    tasa_interes_ea: Decimal | None = Field(None, ge=0)
    cuenta_id: uuid.UUID | None = None
    activa: bool = True


class TarjetaUpdate(BaseModel):
    nombre: str | None = None
    banco: str | None = None
    tipo: TipoTarjeta | None = None
    moneda: str | None = None
    dia_corte: int | None = Field(None, ge=1, le=31)
    dia_pago: int | None = Field(None, ge=1, le=31)
    limite: Decimal | None = Field(None, ge=0)
    tasa_interes: Decimal | None = Field(None, ge=0)
    tasa_interes_ea: Decimal | None = Field(None, ge=0)
    cuenta_id: uuid.UUID | None = None
    activa: bool | None = None


class TarjetaOut(TarjetaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class DeudaIn(BaseModel):
    moneda: str = "COP"
    monto: Decimal = Field(gt=0)
    fecha: date | None = None
    notas: str | None = None


class DeudaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tarjeta_id: uuid.UUID
    moneda: str
    monto: Decimal
    fecha: date
    notas: str | None


class PagoTarjetaIn(BaseModel):
    """Pagar la deuda de una tarjeta de crédito desde una cuenta.

    El pago es un **flujo**: baja el saldo de la cuenta y la deuda vigente. No puede
    superar la deuda de esa moneda (si no, sería un saldo a favor).
    """

    cuenta_id: uuid.UUID
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha: date | None = None
    notas: str | None = None


class PagoTarjetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tarjeta_id: uuid.UUID
    cuenta_id: uuid.UUID | None
    transaccion_id: uuid.UUID | None
    monto: Decimal
    moneda: str
    fecha: date
    notas: str | None


class TarjetaConDeudaOut(TarjetaOut):
    """Tarjeta con su deuda vigente (extracto − pagos) y total en COP."""

    deudas: list[DeudaOut] = []
    pagos: list[PagoTarjetaOut] = []
    # Vigente = extracto − pagos posteriores (lo que se debe hoy)
    deuda_por_moneda: dict[str, float] = {}
    # El desglose, para que el número no parezca inventado
    extracto_por_moneda: dict[str, float] = {}
    pagos_por_moneda: dict[str, float] = {}
    deuda_total_cop: float | None = None
    cuenta_nombre: str | None = None


# --- suscripciones ---


class SuscripcionIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    periodicidad: Periodicidad = Periodicidad.MENSUAL
    fecha_inicio: date | None = None
    proximo_pago: date | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    # De dónde sale el dinero: sin esto, cada gasto que genera el job no tocaba
    # ninguna cuenta y aparecía como «movimiento sin cuenta».
    cuenta_id: uuid.UUID | None = None
    estado: EstadoSuscripcion = EstadoSuscripcion.ACTIVA
    notas: str | None = None


class SuscripcionUpdate(BaseModel):
    nombre: str | None = None
    monto: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    periodicidad: Periodicidad | None = None
    fecha_inicio: date | None = None
    proximo_pago: date | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    estado: EstadoSuscripcion | None = None
    notas: str | None = None


class SuscripcionOut(SuscripcionIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class SaludOut(BaseModel):
    """Estado del servicio. `base` es el de la **base de datos**, no el del proceso."""

    status: str  # 'ok' | 'error'
    app: str
    base: str  # 'ok' | 'sin conexión'
    # Solo el tipo de excepción: el healthcheck no filtra la cadena de conexión
    error: str | None = None


class ReglaOcrIn(BaseModel):
    """Enseñar una regla: «este texto va siempre a esta etiqueta»."""

    # Se normaliza igual que al aprender (mayúsculas, sin acentos ni códigos)
    patron: str = Field(min_length=1, max_length=120)
    etiqueta_id: uuid.UUID


class ReglaOcrUpdate(BaseModel):
    patron: str | None = Field(default=None, min_length=1, max_length=120)
    etiqueta_id: uuid.UUID | None = None


class ReglaOcrOut(BaseModel):
    id: uuid.UUID
    patron: str
    etiqueta_id: uuid.UUID
    # Dónde cae la regla, para que la interfaz muestre «Mercado › Carnes»
    etiqueta_nombre: str | None = None
    categoria_id: uuid.UUID | None = None
    categoria_nombre: str | None = None
    # Cuántas veces la ha usado el clasificador
    veces_usada: int
    creada_en: datetime
    actualizada_en: datetime


# --- transacciones ---


class RecurrenciaIn(BaseModel):
    """Convertir el movimiento en un **compromiso que se repite solo**.

    El **día** sale de la fecha del movimiento: la transacción que estás creando es
    el pago de *este* periodo, y el compromiso queda apuntando al siguiente. Por eso
    el job no duplica el de ahora.

    `periodicidad` es un texto porque gastos e ingresos no comparten valores: un
    gasto admite `semanal|mensual|trimestral|semestral|anual` y un ingreso
    `diario|semanal|mensual`. El router lo traduce y avisa si no encaja.
    """

    periodicidad: str = "mensual"


class TransaccionBase(BaseModel):
    tipo: TipoTransaccion
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha: date
    descripcion: str | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    suscripcion_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    # Solo en una transferencia: la cuenta que recibe (el origen va en `cuenta_id`).
    # Las reglas de coherencia las valida el router, que también cubre el PATCH
    # (donde hay que mirar el estado **resultante**, no solo lo que se envía).
    cuenta_destino_id: uuid.UUID | None = None
    notas: str | None = None


class TransaccionIn(TransaccionBase):
    # Al crearla, `recurrencia` la convierte además en un compromiso que se repite
    recurrencia: RecurrenciaIn | None = None


class TransaccionUpdate(BaseModel):
    tipo: TipoTransaccion | None = None
    monto: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    fecha: date | None = None
    descripcion: str | None = None
    categoria_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    suscripcion_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    cuenta_destino_id: uuid.UUID | None = None
    notas: str | None = None


class TransaccionOut(TransaccionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    # Los rellena el servidor cuando el gasto lo genera una póliza o un compromiso
    poliza_id: uuid.UUID | None = None
    ingreso_recurrente_id: uuid.UUID | None = None


# --- pólizas de seguro y beneficiarios ---

TIPOS_POLIZA = ("vida", "salud", "vehiculo", "hogar", "otro")


class BeneficiarioIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    parentesco: str | None = Field(default=None, max_length=60)
    porcentaje: Decimal | None = Field(default=None, ge=0, le=100)


class BeneficiarioOut(BeneficiarioIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    poliza_id: uuid.UUID


class AseguradoIn(BaseModel):
    """Persona cubierta por la póliza (una póliza familiar cubre a varias)."""

    nombre: str = Field(min_length=1, max_length=120)
    parentesco: str | None = Field(default=None, max_length=60)
    fecha_nacimiento: date | None = None
    es_titular: bool = False

    @model_validator(mode="after")
    def _validar_nacimiento(self) -> AseguradoIn:
        # `hoy()` respeta FINANZAS_TIMEZONE; `date.today()` usa la del servidor y
        # podía rechazar un nacimiento de hoy (o aceptar uno de mañana)
        if self.fecha_nacimiento and self.fecha_nacimiento > hoy():
            raise ValueError("La fecha de nacimiento no puede estar en el futuro")
        return self


class AseguradoOut(AseguradoIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    poliza_id: uuid.UUID


class PolizaIn(BaseModel):
    tipo: Literal["vida", "salud", "vehiculo", "hogar", "otro"] = "vida"
    aseguradora: str = Field(min_length=1, max_length=120)
    numero_poliza: str | None = Field(default=None, max_length=60)
    # Persona asegurada (vida/salud/hogar) o tomador del vehículo
    asegurado_nombre: str | None = Field(default=None, max_length=120)
    # Bien asegurado (vehículo)
    placa: str | None = Field(default=None, max_length=10)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=60)
    anio: int | None = Field(default=None, ge=1900, le=2100)
    valor_asegurado: Decimal | None = Field(default=None, gt=0)
    # Prima y periodicidad
    prima: Decimal = Field(gt=0)
    moneda: str = "COP"
    periodicidad: Periodicidad = Periodicidad.MENSUAL
    # Vigencia
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    proximo_pago: date | None = None
    renovacion_automatica: bool = False
    categoria_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    estado: EstadoSuscripcion = EstadoSuscripcion.ACTIVA
    notas: str | None = None

    @model_validator(mode="after")
    def _validar_vigencia(self) -> PolizaIn:
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin no puede ser anterior a la de inicio")
        return self


class PolizaUpdate(BaseModel):
    tipo: Literal["vida", "salud", "vehiculo", "hogar", "otro"] | None = None
    aseguradora: str | None = Field(default=None, min_length=1, max_length=120)
    numero_poliza: str | None = Field(default=None, max_length=60)
    asegurado_nombre: str | None = Field(default=None, max_length=120)
    placa: str | None = Field(default=None, max_length=10)
    marca: str | None = Field(default=None, max_length=60)
    modelo: str | None = Field(default=None, max_length=60)
    anio: int | None = Field(default=None, ge=1900, le=2100)
    valor_asegurado: Decimal | None = Field(default=None, gt=0)
    prima: Decimal | None = Field(default=None, gt=0)
    moneda: str | None = None
    periodicidad: Periodicidad | None = None
    fecha_inicio: date | None = None
    fecha_fin: date | None = None
    proximo_pago: date | None = None
    renovacion_automatica: bool | None = None
    categoria_id: uuid.UUID | None = None
    etiqueta_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    estado: EstadoSuscripcion | None = None
    notas: str | None = None


class PolizaOut(PolizaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    creada_en: datetime
    beneficiarios: list[BeneficiarioOut] = []
    asegurados: list[AseguradoOut] = []
    # Prima normalizada a mes y a COP (None si no hay tasa para su moneda)
    prima_mensual_cop: float | None = None
    # Etiqueta legible: «Vehículo ABC123 (Sura)»
    titulo: str


class PolizaPorTipoOut(BaseModel):
    """Costo de los seguros de un tipo (lo que se ve en Reportes)."""

    tipo: str
    polizas: int
    prima_mensual_cop: float
    prima_anual_cop: float


class PolizaResumenOut(BaseModel):
    """Cuánto cuestan los seguros: prima mensual y anual, normalizada a COP."""

    polizas_activas: int
    prima_mensual_cop: float
    prima_anual_cop: float
    sin_tasa: list[str]  # monedas sin tasa de cambio registrada
    por_tipo: list[PolizaPorTipoOut] = []


# --- ingresos recurrentes ---


class IngresoRecurrenteIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto: Decimal = Field(gt=0)
    moneda: str = "COP"
    periodicidad: PeriodicidadIngreso
    # mensual: 1-31 · semanal: 0 (lunes) a 6 (domingo) · diario: ignorado
    dia: int | None = None
    categoria_id: uuid.UUID | None = None
    # En qué cuenta entra: sin esto, el ingreso generado no tocaba ninguna cuenta
    cuenta_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _validar_dia(self) -> IngresoRecurrenteIn:
        if self.periodicidad == PeriodicidadIngreso.MENSUAL and not (self.dia is not None and 1 <= self.dia <= 31):
            raise ValueError("Para periodicidad mensual, 'dia' debe estar entre 1 y 31")
        if self.periodicidad == PeriodicidadIngreso.SEMANAL and not (self.dia is not None and 0 <= self.dia <= 6):
            raise ValueError("Para periodicidad semanal, 'dia' debe ser 0 (lunes) a 6 (domingo)")
        return self


class IngresoRecurrenteUpdate(BaseModel):
    nombre: str | None = None
    monto: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    periodicidad: PeriodicidadIngreso | None = None
    dia: int | None = None
    categoria_id: uuid.UUID | None = None
    cuenta_id: uuid.UUID | None = None
    activa: bool | None = None


class IngresoRecurrenteOut(IngresoRecurrenteIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    proxima_ejecucion: date
    activa: bool


# --- etiquetas y subetiquetas ---


class EtiquetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    color: str | None = None
    # La categoría a la que pertenece la etiqueta
    categoria_id: uuid.UUID | None = None
    # NULL = etiqueta; con valor = subetiqueta de esa etiqueta
    padre_id: uuid.UUID | None = None


class EtiquetaUpdate(BaseModel):
    nombre: str | None = None
    color: str | None = None
    categoria_id: uuid.UUID | None = None
    padre_id: uuid.UUID | None = None


class EtiquetaOut(EtiquetaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class DiccionarioEtiquetasOut(BaseModel):
    """Resultado de sembrar las etiquetas que el diccionario del OCR reconoce."""

    total_creadas: int
    creadas: list[EtiquetaOut] = []


# --- alertas ---


class AlertaOut(BaseModel):
    tipo: str  # 'suscripcion' | 'tarjeta_pago' | 'tarjeta_corte'
    titulo: str
    fecha: date
    dias_restantes: int  # negativo = ya vencido
    monto: Decimal | None = None
    moneda: str | None = None
    # 'extracto' cuando el monto y la fecha salen de un extracto leído, no del día de pago
    origen: str | None = None


# --- reportes ---


class ReporteMesOut(BaseModel):
    mes: str
    ingresos: float
    gastos: float
    balance: float


class ReporteCategoriaOut(BaseModel):
    categoria: str
    etiqueta: str | None = None
    tipo: str
    total: float


# --- facturas (PDF) ---


class FacturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    nombre_archivo: str
    texto_extraido: str | None
    monto_detectado: Decimal | None
    fecha_detectada: date | None
    transaccion_id: uuid.UUID | None
    creada_en: datetime


class AsociarFacturaIn(BaseModel):
    transaccion_id: uuid.UUID


# --- líneas de factura (OCR por línea) ---


class FacturaLineaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    factura_id: uuid.UUID
    descripcion: str
    cantidad: Decimal | None
    valor_unitario: Decimal | None
    valor_total: Decimal
    etiqueta_id: uuid.UUID | None
    origen: str  # historial | diccionario | embeddings | manual | sin_clasificar
    confianza: Decimal | None
    orden: int
    transaccion_id: uuid.UUID | None


class FacturaDetalleOut(FacturaOut):
    """Factura con sus líneas detectadas por OCR."""

    lineas: list[FacturaLineaOut] = []
    tipo_documento: str | None = None  # mercado | gasolina | servicios | restaurante | otro


class MovimientoOut(BaseModel):
    """Un movimiento del listado: una transacción suelta o una compra agrupada.

    Una compra (factura confirmada) se colapsa en **un solo** movimiento: las
    transacciones de sus artículos se agrupan, el monto es la suma y `articulos`
    dice cuántos artículos hay detrás. Así el listado no se llena con 120 filas.
    """

    id: uuid.UUID | None = None  # la transacción representativa (la asociada)
    ids: list[uuid.UUID] = []  # todas las transacciones que agrupa
    tipo: str
    monto: Decimal
    fecha: date
    descripcion: str | None = None
    categoria_id: uuid.UUID | None = None
    categoria: str | None = None
    etiqueta_id: uuid.UUID | None = None
    etiquetas: list[str] = []  # etiquetas del detalle (para una compra)
    factura_id: uuid.UUID | None = None
    articulos: int = 0  # 0 si no es una compra
    agrupada: bool = False
    cuenta_id: uuid.UUID | None = None
    cuenta_destino_id: uuid.UUID | None = None  # solo transferencias
    tarjeta_id: uuid.UUID | None = None
    moneda: str = "COP"
    notas: str | None = None
    # Texto para el buscador: descripción + categoría + etiquetas + artículos del detalle
    busqueda: str = ""
    suscripcion_id: uuid.UUID | None = None
    ingreso_recurrente_id: uuid.UUID | None = None
    poliza_id: uuid.UUID | None = None


class ArticuloDetalleOut(BaseModel):
    id: uuid.UUID
    descripcion: str
    cantidad: Decimal | None
    valor_unitario: Decimal | None
    valor_total: Decimal
    origen: str


class GrupoDetalleOut(BaseModel):
    etiqueta: str | None
    categoria: str | None
    total: Decimal
    porcentaje: Decimal
    articulos: list[ArticuloDetalleOut]


class DetalleFacturaOut(BaseModel):
    factura_id: uuid.UUID
    descripcion: str | None
    total: Decimal
    articulos: int
    grupos: list[GrupoDetalleOut]


class UnificarOut(BaseModel):
    transaccion_id: uuid.UUID
    creada: bool  # False si ya estaba unificada
    unificados: int  # transacciones individuales borradas
    total: Decimal


class ParsearLineasIn(BaseModel):
    """`texto` permite re-parsear un texto distinto del guardado (opcional)."""

    texto: str | None = None


class LineaUpdateIn(BaseModel):
    """Editar una línea. `etiqueta_id` corregida se aprende en `reglas_ocr`."""

    descripcion: str | None = None
    valor_total: Decimal | None = Field(default=None, gt=0)
    etiqueta_id: uuid.UUID | None = None


class AsignarEtiquetaIn(BaseModel):
    """Asignar **una etiqueta a muchas líneas** de una vez.

    Pensado para una tira larga de mercado: en lugar de corregir 30 líneas una a
    una, se elige la etiqueta y se aplica a las que están sin clasificar. Cada
    asignación se **aprende** en `reglas_ocr`, así que la próxima vez el
    clasificador ya las reconoce por historial.

    - `linea_ids` vacío o ausente = todas las líneas pendientes que encajen.
    - `solo_sin_clasificar` (por defecto) respeta lo que el diccionario ya acertó:
      para sobrescribir todo hay que pedirlo explícitamente.
    - `etiqueta_id: null` sirve para **quitar** la etiqueta de esas líneas.
    """

    etiqueta_id: uuid.UUID | None = None
    linea_ids: list[uuid.UUID] | None = None
    solo_sin_clasificar: bool = True


class ConfirmarLineasIn(BaseModel):
    """`linea_ids` vacío o ausente = todas las líneas sin confirmar.

    `tarjeta_id` y `cuenta_id` son excluyentes en la práctica: si la tarjeta es de
    **débito**, la transacción hereda la cuenta de la tarjeta (es un instrumento de
    esa cuenta). `fecha` permite registrar la compra en su día real cuando el
    recibo no trae fecha legible; por defecto se usa la detectada o la de hoy.
    """

    linea_ids: list[uuid.UUID] | None = None
    cuenta_id: uuid.UUID | None = None
    tarjeta_id: uuid.UUID | None = None
    fecha: date | None = None
    # Respaldo para las líneas que sigan sin etiqueta: así una compra que el
    # diccionario no conoce no genera gastos **sin categoría** (invisibles para
    # los reportes y los presupuestos). Si se indica `etiqueta_id`, su categoría
    # manda; si solo hay `categoria_id`, el gasto queda en esa categoría.
    etiqueta_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None


class ConfirmarTotalIn(ConfirmarLineasIn):
    """Cerrar el recibo como **una sola** transacción con el total.

    Las líneas quedan como **detalle** de ese gasto (no desaparecen: siguen ahí y
    enlazadas a la misma transacción). Si no se indica `monto`, se usa la suma de
    las líneas pendientes, que es lo que ves en la tabla; `monto` permite usar el
    total que trae el recibo cuando el OCR lo detectó distinto.
    """

    monto: Decimal | None = Field(default=None, gt=0)
    # Por defecto se propone el nombre del artículo (si es uno) o «Compra de N artículos»
    descripcion: str | None = Field(default=None, max_length=200)


# --- presupuestos ---


class PresupuestoIn(BaseModel):
    categoria_id: uuid.UUID
    monto_limite: Decimal = Field(gt=0)
    moneda: str = "COP"


class PresupuestoUpdate(BaseModel):
    monto_limite: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    activo: bool | None = None


class PresupuestoOut(BaseModel):
    id: uuid.UUID
    categoria_id: uuid.UUID
    categoria_nombre: str
    monto_limite: Decimal
    moneda: str
    gastado: float
    restante: float
    porcentaje: float
    activo: bool


# --- importar CSV ---


class ImportarFilaIn(BaseModel):
    fecha: date
    descripcion: str | None = None
    monto: Decimal = Field(gt=0)
    tipo: TipoTransaccion
    moneda: str = "COP"
    categoria_id: uuid.UUID | None = None


class ImportarConfirmarIn(BaseModel):
    filas: list[ImportarFilaIn]


class ImportarPreviewOut(BaseModel):
    filas: list[ImportarFilaIn]
    total: int


class ImportarResultadoOut(BaseModel):
    creadas: int


# --- mercado (productos, precios, lista) ---


class ProductoIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    unidad: str | None = None


class ProductoUpdate(BaseModel):
    nombre: str | None = None
    unidad: str | None = None


class ProductoOut(ProductoIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID


class PrecioIn(BaseModel):
    tienda: str | None = None
    precio: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha: date | None = None


class PrecioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    producto_id: uuid.UUID
    tienda: str | None
    precio: Decimal
    moneda: str
    fecha: date


class ComparativoTiendaOut(BaseModel):
    tienda: str
    precio: Decimal
    moneda: str
    fecha: date


class ComparativoOut(BaseModel):
    producto_id: uuid.UUID
    producto_nombre: str
    tiendas: list[ComparativoTiendaOut]
    mas_barata: str | None = None


class ItemListaIn(BaseModel):
    producto_id: uuid.UUID | None = None
    nombre: str = Field(min_length=1, max_length=120)
    cantidad: Decimal = Field(default=Decimal("1"), gt=0)
    precio_estimado: Decimal | None = None


class ItemListaUpdate(BaseModel):
    nombre: str | None = None
    cantidad: Decimal | None = Field(None, gt=0)
    precio_estimado: Decimal | None = None
    comprado: bool | None = None


class ItemListaOut(ItemListaIn):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID
    comprado: bool


class ListaMercadoOut(BaseModel):
    items: list[ItemListaOut]
    total_estimado: float
    pendientes: int


# --- monedas y tasas de cambio ---


class MonedaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    codigo: str
    nombre: str
    simbolo: str


class TasaIn(BaseModel):
    moneda_origen: str = Field(min_length=3, max_length=3)
    moneda_destino: str = Field(min_length=3, max_length=3)
    tasa: Decimal = Field(gt=0)
    fecha: date | None = None
    fuente: str | None = None


class TasaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    moneda_origen: str
    moneda_destino: str
    tasa: Decimal
    fecha: date
    fuente: str | None


class ConversionOut(BaseModel):
    de: str
    a: str
    monto: Decimal
    tasa: Decimal
    resultado: Decimal


# --- simulador de intereses de tarjeta ---


class SimulacionOut(BaseModel):
    saldo_inicial: Decimal
    tasa_mensual: Decimal
    pago_mensual: Decimal
    meses: int
    total_intereses: Decimal
    total_pagado: Decimal
    viable: bool


# --- proyección de flujo de caja ---


class FlujoMesOut(BaseModel):
    mes: str
    ingresos: float
    gastos_fijos: float
    gastos_variables: float
    gastos: float
    balance: float
    acumulado: float


class FlujoCajaOut(BaseModel):
    # Todo el flujo se expresa en una sola moneda (COP): los importes en otra
    # moneda se convierten con la tasa registrada, y las que no la tienen se
    # informan en `sin_tasa` en vez de sumarse en crudo.
    moneda: str = "COP"
    sin_tasa: list[str] = []
    meses: list[FlujoMesOut]
    gasto_variable_promedio: float
    total_ingresos: float
    total_gastos: float
    balance_final: float


# --- metas de ahorro ---


class MetaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=120)
    monto_objetivo: Decimal = Field(gt=0)
    moneda: str = "COP"
    fecha_limite: date | None = None
    notas: str | None = None


class MetaUpdate(BaseModel):
    nombre: str | None = None
    monto_objetivo: Decimal | None = Field(None, gt=0)
    moneda: str | None = None
    fecha_limite: date | None = None
    notas: str | None = None


class AporteIn(BaseModel):
    monto: Decimal = Field(gt=0)
    fecha: date | None = None
    notas: str | None = None


class AporteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    meta_id: uuid.UUID
    monto: Decimal
    fecha: date
    notas: str | None


class MetaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    monto_objetivo: Decimal
    moneda: str
    monto_actual: float
    restante: float
    porcentaje: float
    fecha_limite: date | None
    aporte_mensual_sugerido: float | None
    completada: bool
    notas: str | None


# --- notificaciones (Telegram / email) ---


class NotificacionesIn(BaseModel):
    # `ambos` = telegram + correo (compatibilidad); `todos` = los tres canales.
    canal: Literal["telegram", "email", "whatsapp", "ambos", "todos"] = "telegram"
    telegram_chat_id: str | None = None
    whatsapp_numero: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    dias_anticipacion: int = Field(5, ge=1, le=60)
    activo: bool = False


class NotificacionesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    canal: str
    telegram_chat_id: str | None
    whatsapp_numero: str | None
    email: str | None
    dias_anticipacion: int
    activo: bool
    ultima_notificacion: date | None


class PruebaNotificacionOut(BaseModel):
    enviados: list[str]
    alertas: int


class ChatTelegramOut(BaseModel):
    chat_id: str
    nombre: str


class DetectarTelegramOut(BaseModel):
    chats: list[ChatTelegramOut]


# --- cuentas, saldos y consolidado ---


class CuentaIn(BaseModel):
    nombre: str = Field(min_length=1, max_length=80)
    tipo: str = "efectivo"
    saldo_inicial: Decimal = Decimal("0")
    moneda: str = "COP"
    activa: bool = True


class CuentaUpdate(BaseModel):
    nombre: str | None = None
    tipo: str | None = None
    saldo_inicial: Decimal | None = None
    moneda: str | None = None
    activa: bool | None = None


class CuentaOut(BaseModel):
    id: uuid.UUID
    nombre: str
    tipo: str
    moneda: str
    activa: bool
    saldo_inicial: Decimal
    ingresos: float
    gastos: float
    # Las transferencias mueven el saldo sin ser ingreso ni gasto: se informan
    # aparte para que el saldo no parezca inventado.
    transferencias_enviadas: float = 0.0
    transferencias_recibidas: float = 0.0
    saldo_actual: float


class SaldoResumenOut(BaseModel):
    saldo_total: float
    saldo_inicial_total: float
    ingresos_total: float
    gastos_total: float
    sin_cuenta: float
    sin_cuenta_movimientos: int
    sobregirado: bool
    cuentas: list[CuentaOut]


class ConsolidadoMesOut(BaseModel):
    mes: str
    saldo_inicial: float
    ingresos: float
    gastos: float
    balance: float
    saldo_final: float


class ConsolidadoOut(BaseModel):
    meses: list[ConsolidadoMesOut]
    saldo_actual: float


class MotivoOut(BaseModel):
    tipo: str
    etiqueta: str
    monto: float
    detalle: str | None = None


class ProximoIngresoOut(BaseModel):
    nombre: str
    monto: float
    fecha: date


class DiagnosticoOut(BaseModel):
    saldo_actual: float
    sobregirado: bool
    tiene_cuentas: bool
    sin_cuenta_movimientos: int
    proximo_ingreso: ProximoIngresoOut | None = None
    ingresos_mes: float
    gastos_mes: float
    balance_mes: float
    ingresos_mes_anterior: float
    gastos_mes_anterior: float
    gastos_fijos: float
    motivos: list[str]
    top_categorias: list[MotivoOut]


class AdoptarMovimientosOut(BaseModel):
    asignados: int
    cuenta: str
    saldo_actual: float
