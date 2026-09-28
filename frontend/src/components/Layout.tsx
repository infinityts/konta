import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'

const items = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/tarjetas', label: 'Tarjetas', end: false },
  { to: '/suscripciones', label: 'Suscripciones', end: false },
  { to: '/ingresos-recurrentes', label: 'Ingresos recurrentes', end: false },
  { to: '/transacciones', label: 'Transacciones', end: false },
  { to: '/etiquetas', label: 'Etiquetas', end: false },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  function salir() {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white p-4">
        <h1 className="text-lg font-semibold">Konta</h1>
        <nav className="mt-6 flex flex-col gap-1">
          {items.map((i) => (
            <NavLink
              key={i.to}
              to={i.to}
              end={i.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm ${
                  isActive
                    ? 'bg-indigo-50 font-medium text-indigo-700'
                    : 'text-slate-600 hover:bg-slate-50'
                }`
              }
            >
              {i.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex-1">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-4">
          <p className="text-sm text-slate-500">Hola, {user?.nombre ?? 'usuario'}</p>
          <button
            onClick={salir}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Salir
          </button>
        </header>
        <main className="p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
