"""Categorías por defecto para usuarios nuevos."""

DEFAULT_CATEGORIAS: list[dict] = [
    # gastos
    {"nombre": "Suscripciones", "tipo": "gasto", "icono": "repeat", "color": "#6366f1"},
    {"nombre": "Mercado", "tipo": "gasto", "icono": "cart", "color": "#22c55e"},
    {"nombre": "Transporte", "tipo": "gasto", "icono": "car", "color": "#f59e0b"},
    {"nombre": "Vivienda", "tipo": "gasto", "icono": "home", "color": "#0ea5e9"},
    {"nombre": "Restaurantes", "tipo": "gasto", "icono": "utensils", "color": "#ef4444"},
    {"nombre": "Salud", "tipo": "gasto", "icono": "heart", "color": "#ec4899"},
    {"nombre": "Entretenimiento", "tipo": "gasto", "icono": "gamepad", "color": "#a855f7"},
    {"nombre": "Telefonía", "tipo": "gasto", "icono": "phone", "color": "#0891b2"},
    {"nombre": "Otros gastos", "tipo": "gasto", "icono": "ellipsis", "color": "#64748b"},
    # ingresos
    {"nombre": "Salario", "tipo": "ingreso", "icono": "wallet", "color": "#10b981"},
    {"nombre": "Otros ingresos", "tipo": "ingreso", "icono": "plus", "color": "#14b8a6"},
]
