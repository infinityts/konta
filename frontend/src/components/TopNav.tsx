import { useEffect, useRef, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { GRUPOS, RESUMEN, grupoDeRuta } from '../nav'
import { KIcono } from './Marca'

const claseItem = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm ${
    isActive ? 'bg-indigo-50 font-medium text-indigo-700' : 'text-slate-700 hover:bg-slate-100'
  }`

/**
 * Barra superior de navegación.
 *
 * - Escritorio: `Resumen` + 5 grupos; el submenú abre al **pasar el mouse**
 *   (y con clic, para teclado y pantallas táctiles).
 * - Móvil (<768px): botón hamburguesa con panel lateral y grupos en acordeón.
 * - Cierra al navegar, al hacer clic fuera y con `Esc`.
 */
export default function TopNav() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  const [abierto, setAbierto] = useState<string | null>(null)
  const [panelMovil, setPanelMovil] = useState(false)
  const [grupoMovil, setGrupoMovil] = useState<string | null>(null)
  const navRef = useRef<HTMLElement>(null)

  const grupoActivo = grupoDeRuta(pathname)

  // Cerrar todo al cambiar de ruta
  useEffect(() => {
    setAbierto(null)
    setPanelMovil(false)
  }, [pathname])

  // Cerrar el submenú al hacer clic fuera de la navegación
  useEffect(() => {
    function alClicFuera(e: MouseEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) setAbierto(null)
    }
    document.addEventListener('mousedown', alClicFuera)
    return () => document.removeEventListener('mousedown', alClicFuera)
  }, [])

  // Esc cierra submenú y panel móvil
  useEffect(() => {
    function alTeclado(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        setAbierto(null)
        setPanelMovil(false)
      }
    }
    document.addEventListener('keydown', alTeclado)
    return () => document.removeEventListener('keydown', alTeclado)
  }, [])

  // Con el panel móvil abierto no se hace scroll del fondo
  useEffect(() => {
    document.body.style.overflow = panelMovil ? 'hidden' : ''
    return () => {
      document.body.style.overflow = ''
    }
  }, [panelMovil])

  function salir() {
    logout()
    navigate('/login')
  }

  const marca = (
    <NavLink to="/" className="flex items-center gap-2" aria-label="Konta, ir al resumen">
      <KIcono className="h-7 w-auto" />
      <span className="text-lg font-bold tracking-tight text-slate-900">
        Kon<span className="text-indigo-600">ta</span>
      </span>
    </NavLink>
  )

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200 bg-white">
      <div className="flex h-16 items-center gap-6 px-5">
        {marca}

        {/* ---------- Escritorio ---------- */}
        <nav
          ref={navRef}
          onMouseLeave={() => setAbierto(null)}
          className="hidden flex-1 items-center gap-1 md:flex"
        >
          <NavLink
            to={RESUMEN.to}
            end
            className={({ isActive }) =>
              `rounded-lg px-3 py-2 text-sm ${
                isActive
                  ? 'bg-indigo-50 font-semibold text-indigo-700'
                  : 'text-slate-700 hover:bg-slate-100'
              }`
            }
          >
            {RESUMEN.label}
          </NavLink>

          {GRUPOS.map((g) => {
            const esteAbierto = abierto === g.id
            const activo = grupoActivo === g.id
            return (
              <div key={g.id} className="relative" onMouseEnter={() => setAbierto(g.id)}>
                <button
                  type="button"
                  aria-haspopup="true"
                  aria-expanded={esteAbierto}
                  onClick={() => setAbierto(esteAbierto ? null : g.id)}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm ${
                    esteAbierto || activo
                      ? 'bg-indigo-50 font-semibold text-indigo-700'
                      : 'text-slate-700 hover:bg-slate-100'
                  }`}
                >
                  {g.label}
                  <span
                    className={`text-[9px] transition-transform ${esteAbierto ? 'rotate-180' : ''}`}
                  >
                    ▼
                  </span>
                </button>

                {esteAbierto && (
                  <div className="absolute left-0 top-full z-50 pt-2">
                    <div className="min-w-56 rounded-xl border border-slate-200 bg-white p-1.5 shadow-xl">
                      {g.items.map((it) => (
                        <NavLink key={it.to} to={it.to} className={claseItem}>
                          <span className="w-5 text-center">{it.icono}</span>
                          {it.label}
                        </NavLink>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </nav>

        {/* ---------- Usuario ---------- */}
        <div className="ml-auto flex items-center gap-2 md:gap-3">
          <span className="hidden text-sm text-slate-500 sm:inline">
            Hola, {user?.nombre ?? 'usuario'}
          </span>
          <button
            onClick={salir}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50"
          >
            Salir
          </button>
          <button
            onClick={() => setPanelMovil(true)}
            aria-label="Abrir menú"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 md:hidden"
          >
            ☰
          </button>
        </div>
      </div>

      {/* ---------- Panel móvil ---------- */}
      {panelMovil && (
        <div className="fixed inset-0 z-50 bg-white md:hidden">
          <div className="flex h-16 items-center justify-between border-b border-slate-200 px-5">
            {marca}
            <button
              onClick={() => setPanelMovil(false)}
              aria-label="Cerrar menú"
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600"
            >
              ✕
            </button>
          </div>

          <nav className="h-[calc(100vh-4rem)] overflow-y-auto px-4 pb-8">
            <NavLink to={RESUMEN.to} end className={({ isActive }) => `${claseItem({ isActive })} mt-3`}>
              <span className="w-5 text-center">{RESUMEN.icono}</span>
              {RESUMEN.label}
            </NavLink>

            {GRUPOS.map((g) => {
              const abiertoMovil = grupoMovil === g.id
              return (
                <div key={g.id} className="mt-2 border-t border-slate-100 pt-1">
                  <button
                    type="button"
                    aria-expanded={abiertoMovil}
                    onClick={() => setGrupoMovil(abiertoMovil ? null : g.id)}
                    className="flex w-full items-center justify-between py-3 text-sm font-medium text-slate-800"
                  >
                    <span className={grupoActivo === g.id ? 'text-indigo-700' : ''}>{g.label}</span>
                    <span className="text-[10px] text-slate-400">{abiertoMovil ? '▲' : '▼'}</span>
                  </button>
                  {abiertoMovil && (
                    <div className="pb-2">
                      {g.items.map((it) => (
                        <NavLink key={it.to} to={it.to} className={claseItem}>
                          <span className="w-5 text-center">{it.icono}</span>
                          {it.label}
                        </NavLink>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </nav>
        </div>
      )}
    </header>
  )
}
