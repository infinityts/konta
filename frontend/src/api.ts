const API_URL = import.meta.env.VITE_API_URL ?? '/api'

/** Los errores de validación de la API, dichos en cristiano. */
const ERRORES_DE_CAMPO: Record<string, string> = {
  missing: 'falta un dato obligatorio',
  decimal_parsing: 'no es un número válido',
  int_parsing: 'no es un número entero válido',
  greater_than: 'tiene que ser mayor que cero',
  less_than: 'es demasiado grande',
  string_too_short: 'es demasiado corto',
  string_too_long: 'es demasiado largo',
  date_parsing: 'no es una fecha válida',
  enum: 'no es una de las opciones válidas',
}

/**
 * Traduce el error de la API a algo que el usuario pueda leer.
 *
 * FastAPI devuelve `detail` de dos formas: un **texto** cuando el error es nuestro (401,
 * 404, 422 del router) y una **lista de objetos** cuando falla la validación del esquema.
 * Al hacer `new Error(detail)` con la lista, el navegador la convertía en el texto
 * «[object Object]» —pasó al insertar un gasto— y no había manera de saber qué campo
 * estaba mal.
 */
export function mensajeDeError(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const partes = detail
      .map((d) => {
        const fallo = d as { loc?: unknown[]; msg?: string; type?: string }
        const campo = (fallo.loc ?? []).filter((p) => p !== 'body' && p !== 'query').join('.')
        const limpio = (fallo.msg ?? '').replace(/^Value error, /, '')
        const msg = ERRORES_DE_CAMPO[fallo.type ?? ''] || limpio
        return campo ? `${campo}: ${msg}` : msg
      })
      .filter(Boolean)
    if (partes.length) return `Revisa los datos: ${partes.join('; ')}`
  }
  if (detail) return JSON.stringify(detail)
  return `HTTP ${status}`
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('konta_token')
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(mensajeDeError(body, res.status))
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  const token = localStorage.getItem('konta_token')
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: formData,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    // Si el que corta es nginx, la respuesta es una página HTML: `res.json()` falla y el
    // usuario acabaría viendo «HTTP 413», que no le dice qué hacer.
    if (res.status === 413) {
      throw new Error(
        'El archivo es muy grande (máximo 15 MB). Bájale la calidad a la foto o recórtala.'
      )
    }
    if (res.status === 504) {
      throw new Error(
        'El archivo tardó demasiado en leerse (suele ser un escaneado con muchas páginas). ' +
          'Prueba a subir solo las páginas que necesitas.'
      )
    }
    throw new Error(mensajeDeError(body, res.status))
  }
  return res.json() as Promise<T>
}

export async function apiDownload(path: string, filename: string): Promise<void> {
  const token = localStorage.getItem('konta_token')
  const res = await fetch(`${API_URL}${path}`, {
    headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
