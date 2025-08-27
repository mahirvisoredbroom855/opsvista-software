
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export function Protected() {
  const { ready, user } = useAuth()
  const loc = useLocation()
  if (!ready) return <div className="card">Loading…</div>
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />
  return <Outlet />
}
