import { useEffect, useState } from 'react'
import { useAuth } from '../auth'
import { api } from '../api'

interface Categoria {
  id: string
  nombre: string
  tipo: string
  icono: string | null
  color: string | null
}

export default function Dashboard() {
  const { user, logout } = useAuth()
  const [categorias, setCategorias] = useState<Categoria[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    api<Categoria[]>('/categorias')
      .then(setCategorias)
      .catch((e) => setError(e.message))
  }, [])

  return (
    <div className="min-h-screen">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
        <div>
          <h1 className="text-lg font-semibold">Konta</h1>
          <p className="text-sm text-slate-500">Hola, {user?.nombre ?? 'usuario'}</p>
        </div>
        <button
          onClick={logout}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
        >
          Salir
        </button>
      </header>

      <main className="mx-auto max-w-5xl px-6 py-8">
        <h2 className="text-xl font-semibold">Resumen</h2>
        <p className="mt-1 text-sm text-slate-500">
          Aquí verás tus KPIs (gasto del mes, suscripciones activas, etc.) — próximo paso.
        </p>

        <div className="mt-8">
          <h3 className="font-medium text-slate-700">Tus categorías</h3>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-3 flex flex-wrap gap-2">
            {categorias.map((c) => (
              <span
                key={c.id}
                className="rounded-full border border-slate-200 bg-white px-3 py-1 text-sm text-slate-700"
              >
                {c.nombre} · {c.tipo}
              </span>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
