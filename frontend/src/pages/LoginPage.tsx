
import { FormEvent, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../modules/auth/AuthContext'

export default function LoginPage() {
  const { signIn, signUp } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [mode, setMode] = useState<'login'|'signup'>('login')
  const [error, setError] = useState<string | null>(null)
  const nav = useNavigate()
  const loc = useLocation() as any
  const redirectTo = loc.state?.from || '/dashboard'

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    const action = mode === 'login' ? signIn : signUp
    const res = await action(email, password)
    if (res.error) setError(res.error)
    else nav(redirectTo, { replace: true })
  }

  return (
    <div className="card" style={{maxWidth:480, margin:'60px auto'}}>
      <h2>{mode === 'login' ? 'Sign in' : 'Create account'}</h2>
      <form onSubmit={onSubmit}>
        <div className="field">
          <label>Email</label>
          <input type="email" value={email} onChange={e=>setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
        </div>
        {error && <div style={{color:'#ff8080', marginBottom:10}}>{error}</div>}
        <div className="row">
          <button type="submit">{mode==='login' ? 'Sign in' : 'Sign up'}</button>
          <button type="button" className="secondary" onClick={()=>setMode(mode==='login'?'signup':'login')}>
            {mode==='login' ? 'Need an account?' : 'Already have an account?'}
          </button>
        </div>
        <div className="muted" style={{marginTop:10}}>Supabase email/password auth</div>
      </form>
    </div>
  )
}
