import type { ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Categorias from './pages/Categorias'
import Cuentas from './pages/Cuentas'
import Dashboard from './pages/Dashboard'
import Etiquetas from './pages/Etiquetas'
import Facturas from './pages/Facturas'
import FlujoCaja from './pages/FlujoCaja'
import Importar from './pages/Importar'
import IngresosRecurrentes from './pages/IngresosRecurrentes'
import Login from './pages/Login'
import Mercado from './pages/Mercado'
import Metas from './pages/Metas'
import Monedas from './pages/Monedas'
import Notificaciones from './pages/Notificaciones'
import Presupuestos from './pages/Presupuestos'
import Register from './pages/Register'
import Reportes from './pages/Reportes'
import Respaldo from './pages/Respaldo'
import Suscripciones from './pages/Suscripciones'
import Tarjetas from './pages/Tarjetas'
import Transacciones from './pages/Transacciones'

function Protected({ children }: { children: ReactNode }) {
  const { token } = useAuth()
  return token ? <>{children}</> : <Navigate to="/login" replace />
}

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
        <Route path="/" element={<Dashboard />} />
        <Route path="/tarjetas" element={<Tarjetas />} />
        <Route path="/suscripciones" element={<Suscripciones />} />
        <Route path="/ingresos-recurrentes" element={<IngresosRecurrentes />} />
        <Route path="/etiquetas" element={<Etiquetas />} />
        <Route path="/reportes" element={<Reportes />} />
        <Route path="/flujo" element={<FlujoCaja />} />
        <Route path="/presupuestos" element={<Presupuestos />} />
        <Route path="/metas" element={<Metas />} />
        <Route path="/facturas" element={<Facturas />} />
        <Route path="/importar" element={<Importar />} />
        <Route path="/mercado" element={<Mercado />} />
        <Route path="/monedas" element={<Monedas />} />
        <Route path="/respaldo" element={<Respaldo />} />
        <Route path="/notificaciones" element={<Notificaciones />} />
        <Route path="/cuentas" element={<Cuentas />} />
        <Route path="/categorias" element={<Categorias />} />
        <Route path="/transacciones" element={<Transacciones />} />
      </Route>
    </Routes>
  )
}
