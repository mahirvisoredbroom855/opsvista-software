
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../modules/auth/AuthContext'

export function NavBar() {
  const { user, signOut } = useAuth()
  const nav = useNavigate()
  return (
    <div className="nav">
      <NavLink to="/dashboard" className={({isActive}) => isActive ? 'active' : ''}>Dashboard</NavLink>
      <NavLink to="/tasks" className={({isActive}) => isActive ? 'active' : ''}>Tasks</NavLink>
      <NavLink to="/chat" className={({isActive}) => isActive ? 'active' : ''}>RAG Chat</NavLink>
      <div className="right">
        {user ? (
          <button className="secondary" onClick={async () => { await signOut(); nav('/login')}}>
            Logout
          </button>
        ) : (
          <NavLink to="/login" className={({isActive}) => isActive ? 'active' : ''}>Login</NavLink>
        )}
      </div>
    </div>
  )
}
