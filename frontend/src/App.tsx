import { lazy } from 'react'
import { Navigate, Route, Routes, type RouteObject } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Login from './pages/Login'
import Register from './pages/Register'

// Carga diferida: cada página baja su código al entrar.
// El `Suspense` está en `Layout`, así la barra de navegación no parpadea.
const Categorias = lazy(() => import('./pages/Categorias'))
const Cuentas = lazy(() => import('./pages/Cuentas'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const Etiquetas = lazy(() => import('./pages/Etiquetas'))
const Facturas = lazy(() => import('./pages/Facturas'))
const FlujoCaja = lazy(() => import('./pages/FlujoCaja'))
const Importar = lazy(() => import('./pages/Importar'))
const IngresosRecurrentes = lazy(() => import('./pages/IngresosRecurrentes'))
const Mercado = lazy(() => import('./pages/Mercado'))
const Metas = lazy(() => import('./pages/Metas'))
const Monedas = lazy(() => import('./pages/Monedas'))
const Notificaciones = lazy(() => import('./pages/Notificaciones'))
const Presupuestos = lazy(() => import('./pages/Presupuestos'))
const Reportes = lazy(() => import('./pages/Reportes'))
const Respaldo = lazy(() => import('./pages/Respaldo'))
const Suscripciones = lazy(() => import('./pages/Suscripciones'))
const Tarjetas = lazy(() => import('./pages/Tarjetas'))
const Transacciones = lazy(() => import('./pages/Transacciones'))

function Protected({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

const RUTAS: Array<{ path: string; element: RouteObject['element'] }> = [
  { path: '/', element: <Dashboard /> },
  { path: '/tarjetas', element: <Tarjetas /> },
  { path: '/suscripciones', element: <Suscripciones /> },
  { path: '/ingresos-recurrentes', element: <IngresosRecurrentes /> },
  { path: '/etiquetas', element: <Etiquetas /> },
  { path: '/reportes', element: <Reportes /> },
  { path: '/flujo', element: <FlujoCaja /> },
  { path: '/presupuestos', element: <Presupuestos /> },
  { path: '/metas', element: <Metas /> },
  { path: '/facturas', element: <Facturas /> },
  { path: '/importar', element: <Importar /> },
  { path: '/mercado', element: <Mercado /> },
  { path: '/monedas', element: <Monedas /> },
  { path: '/respaldo', element: <Respaldo /> },
  { path: '/notificaciones', element: <Notificaciones /> },
  { path: '/cuentas', element: <Cuentas /> },
  { path: '/categorias', element: <Categorias /> },
  { path: '/transacciones', element: <Transacciones /> },
]

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route
        element={
          <Protected>
            <Layout />
          </Protected>
        }
      >
        {RUTAS.map((r) => (
          <Route key={r.path} path={r.path} element={r.element} />
        ))}
      </Route>
    </Routes>
  )
}
